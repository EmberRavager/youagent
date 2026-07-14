import AppKit
import SwiftUI

struct AuditEvent: Identifiable {
    let id = UUID()
    let timestamp: String
    let source: String
    let outcome: String
    let command: String
    let titles: [String]
}

@MainActor
final class GuardController: ObservableObject {
    @Published var isRunning = false
    @Published var terminateDangerousProcesses = true
    @Published var events: [AuditEvent] = []
    @Published var lastError: String?

    private var process: Process?
    private var refreshTimer: Timer?

    init() {
        refreshEvents()
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.refreshEvents() }
        }
    }

    deinit {
        refreshTimer?.invalidate()
        process?.terminate()
    }

    var auditURL: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".youagent-guard/audit.jsonl")
    }

    func toggleProtection() {
        isRunning ? stop() : start()
    }

    func start() {
        guard process == nil else { return }
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        task.arguments = [
            "youagent-guard",
            "watch",
            "--action",
            terminateDangerousProcesses ? "terminate" : "alert"
        ]

        var environment = ProcessInfo.processInfo.environment
        let commonPaths = ["/opt/homebrew/bin", "/usr/local/bin", "\(FileManager.default.homeDirectoryForCurrentUser.path)/.local/bin"]
        environment["PATH"] = (commonPaths + [environment["PATH"] ?? "/usr/bin:/bin"]).joined(separator: ":")
        task.environment = environment

        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = pipe
        task.terminationHandler = { [weak self] finished in
            Task { @MainActor in
                self?.process = nil
                self?.isRunning = false
                if finished.terminationStatus != 0 {
                    self?.lastError = "Guard exited with status \(finished.terminationStatus). Ensure 'youagent-guard' is installed and available in PATH."
                }
            }
        }

        do {
            try task.run()
            process = task
            isRunning = true
            lastError = nil
        } catch {
            lastError = error.localizedDescription
            showError(error.localizedDescription)
        }
    }

    func stop() {
        process?.terminate()
        process = nil
        isRunning = false
    }

    func restartIfRunning() {
        guard isRunning else { return }
        stop()
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { [weak self] in
            self?.start()
        }
    }

    func openAuditLog() {
        let directory = auditURL.deletingLastPathComponent()
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        if !FileManager.default.fileExists(atPath: auditURL.path) {
            FileManager.default.createFile(atPath: auditURL.path, contents: nil)
        }
        NSWorkspace.shared.open(auditURL)
    }

    func refreshEvents() {
        guard let data = try? Data(contentsOf: auditURL),
              let text = String(data: data, encoding: .utf8) else {
            events = []
            return
        }

        events = text.split(separator: "\n").suffix(20).reversed().compactMap { line in
            guard let payload = try? JSONSerialization.jsonObject(with: Data(line.utf8)) as? [String: Any] else {
                return nil
            }
            let findings = payload["findings"] as? [[String: Any]] ?? []
            return AuditEvent(
                timestamp: payload["timestamp"] as? String ?? "",
                source: payload["source"] as? String ?? "unknown",
                outcome: payload["outcome"] as? String ?? "unknown",
                command: payload["command"] as? String ?? "",
                titles: findings.compactMap { $0["title"] as? String }
            )
        }
    }

    private func showError(_ message: String) {
        let alert = NSAlert()
        alert.messageText = "YouAgent Guard could not start"
        alert.informativeText = message + "\n\nRun 'pip install -e .' in the YouAgent repository first."
        alert.alertStyle = .warning
        alert.runModal()
    }
}

struct GuardPanel: View {
    @ObservedObject var controller: GuardController

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Image(systemName: controller.isRunning ? "shield.checkered" : "shield.slash")
                    .font(.system(size: 30))
                    .foregroundStyle(controller.isRunning ? .green : .secondary)
                VStack(alignment: .leading) {
                    Text("YouAgent Guard").font(.headline)
                    Text(controller.isRunning ? "Protection is active" : "Protection is stopped")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
            }

            Toggle("Terminate dangerous processes", isOn: $controller.terminateDangerousProcesses)
                .onChange(of: controller.terminateDangerousProcesses) { _ in
                    controller.restartIfRunning()
                }

            Button(controller.isRunning ? "Stop Protection" : "Start Protection") {
                controller.toggleProtection()
            }
            .buttonStyle(.borderedProminent)
            .tint(controller.isRunning ? .red : .accentColor)
            .frame(maxWidth: .infinity)

            Divider()
            HStack {
                Text("Recent risk events").font(.subheadline).bold()
                Spacer()
                Button("Audit Log") { controller.openAuditLog() }
                    .buttonStyle(.link)
            }

            if controller.events.isEmpty {
                Text("No risk events recorded.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 60)
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 10) {
                        ForEach(controller.events.prefix(8)) { event in
                            VStack(alignment: .leading, spacing: 3) {
                                HStack {
                                    Text(event.source).bold()
                                    Spacer()
                                    Text(event.outcome).font(.caption)
                                }
                                Text(event.titles.joined(separator: ", "))
                                    .font(.caption)
                                    .foregroundStyle(.orange)
                                Text(event.command)
                                    .font(.system(.caption2, design: .monospaced))
                                    .lineLimit(2)
                                    .textSelection(.enabled)
                            }
                            .padding(8)
                            .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 8))
                        }
                    }
                }
                .frame(maxHeight: 220)
            }

            if let error = controller.lastError {
                Text(error).font(.caption2).foregroundStyle(.red)
            }

            Divider()
            HStack {
                Text("MVP · process monitoring")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                Spacer()
                Button("Quit") { NSApplication.shared.terminate(nil) }
                    .buttonStyle(.link)
            }
        }
        .padding(16)
        .frame(width: 360)
    }
}

@main
struct YouAgentGuardApp: App {
    @StateObject private var controller = GuardController()

    var body: some Scene {
        MenuBarExtra {
            GuardPanel(controller: controller)
        } label: {
            Image(systemName: controller.isRunning ? "shield.fill" : "shield")
        }
        .menuBarExtraStyle(.window)
    }
}
