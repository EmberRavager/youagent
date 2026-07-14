// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "YouAgentGuardApp",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "YouAgentGuardApp", targets: ["YouAgentGuardApp"])
    ],
    targets: [
        .executableTarget(
            name: "YouAgentGuardApp",
            path: "Sources/YouAgentGuardApp"
        )
    ]
)
