import Cocoa
import Darwin
import WebKit

final class StudioBridge: NSObject, WKScriptMessageHandler {
    weak var owner: AppDelegate?

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        owner?.handleStudioMessage(message.body)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, WKNavigationDelegate, WKDownloadDelegate {
    var window: NSWindow!
    var webView: WKWebView!
    var serverProcess: Process?
    var port: Int = 8099
    let preferredPorts = Array(8099...8199)
    let studioBridge = StudioBridge()

    func applicationDidFinishLaunching(_ notification: Notification) {
        port = firstFreePort() ?? 8099
        setupMenu()
        setupWindow()
        showLoadingPage("Starting OpenCore Studio…")
        startBackendServer()
        loadStudioWhenReady()
    }

    func firstFreePort() -> Int? {
        for candidate in preferredPorts {
            if portIsFree(candidate) {
                return candidate
            }
        }
        return nil
    }

    func portIsFree(_ port: Int) -> Bool {
        let fd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP)
        guard fd >= 0 else { return false }
        defer { close(fd) }
        var reuse: Int32 = 1
        setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &reuse, socklen_t(MemoryLayout<Int32>.size))
        var addr = sockaddr_in()
        addr.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = in_port_t(UInt16(port).bigEndian)
        addr.sin_addr = in_addr(s_addr: inet_addr("127.0.0.1"))
        let bound = withUnsafePointer(to: &addr) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.bind(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        return bound == 0
    }

    func supportDirectory() -> URL {
        let url = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
            .appendingPathComponent("OpenCore Studio", isDirectory: true)
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }

    func startBackendServer() {
        guard let resourcePath = Bundle.main.resourcePath else {
            showLoadingPage("Could not find the app Resources folder.")
            return
        }
        let appDir = (resourcePath as NSString).appendingPathComponent("app")
        let appPyPath = (appDir as NSString).appendingPathComponent("app.py")
        guard FileManager.default.fileExists(atPath: appPyPath) else {
            showLoadingPage("Missing embedded backend at \(appPyPath)")
            return
        }

        let pythonPaths = [
            "/usr/bin/python3",
            "/opt/homebrew/bin/python3",
            "/usr/local/bin/python3"
        ]
        var pythonExec = "/usr/bin/python3"
        for path in pythonPaths where FileManager.default.isExecutableFile(atPath: path) {
            pythonExec = path
            break
        }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: pythonExec)
        process.arguments = [appPyPath, "--host", "127.0.0.1", "--port", "\(port)"]
        process.currentDirectoryURL = URL(fileURLWithPath: appDir)

        var env = ProcessInfo.processInfo.environment
        env["PYTHONUNBUFFERED"] = "1"
        env["OCS_WORK_DIR"] = supportDirectory().path
        process.environment = env

        let logURL = supportDirectory().appendingPathComponent("backend.log")
        FileManager.default.createFile(atPath: logURL.path, contents: nil)
        if let handle = try? FileHandle(forWritingTo: logURL) {
            handle.seekToEndOfFile()
            process.standardOutput = handle
            process.standardError = handle
        }

        do {
            try process.run()
            serverProcess = process
            print("[OpenCore Studio] Backend PID \(process.processIdentifier) on 127.0.0.1:\(port)")
        } catch {
            showLoadingPage("Failed to start the Studio backend:\n\(error.localizedDescription)")
        }
    }

    func setupWindow() {
        let rect = NSRect(x: 80, y: 80, width: 1280, height: 860)
        window = NSWindow(
            contentRect: rect,
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.minSize = NSSize(width: 880, height: 620)
        window.center()
        window.title = "OpenCore Studio"
        window.titlebarAppearsTransparent = false
        window.titleVisibility = .visible
        window.isMovableByWindowBackground = true
        window.appearance = NSAppearance(named: .darkAqua)
        window.backgroundColor = NSColor(calibratedRed: 13 / 255, green: 17 / 255, blue: 23 / 255, alpha: 1)
        window.delegate = self

        let config = WKWebViewConfiguration()
        config.preferences.setValue(true, forKey: "developerExtrasEnabled")
        config.preferences.javaScriptCanOpenWindowsAutomatically = true
        studioBridge.owner = self
        config.userContentController.add(studioBridge, name: "studio")

        webView = WKWebView(frame: rect, configuration: config)
        webView.autoresizingMask = [.width, .height]
        webView.navigationDelegate = self
        webView.setValue(false, forKey: "drawsBackground")
        if #available(macOS 13.3, *) {
            webView.isInspectable = true
        }

        window.contentView = webView
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func showLoadingPage(_ message: String) {
        let escaped = message
            .replacingOccurrences(of: "&", with: "&amp;")
            .replacingOccurrences(of: "<", with: "&lt;")
            .replacingOccurrences(of: "\n", with: "<br>")
        let html = """
        <html><body style="margin:0;background:#0d1117;color:#8b949e;font:15px -apple-system,BlinkMacSystemFont,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;text-align:center">
        <div>\(escaped)</div>
        </body></html>
        """
        webView.loadHTMLString(html, baseURL: nil)
    }

    func loadStudioWhenReady() {
        DispatchQueue.global(qos: .userInitiated).async {
            var ready = false
            for _ in 0..<40 {
                if let url = URL(string: "http://127.0.0.1:\(self.port)/api/profiles"),
                   let data = try? Data(contentsOf: url),
                   !data.isEmpty {
                    ready = true
                    break
                }
                Thread.sleep(forTimeInterval: 0.25)
            }
            DispatchQueue.main.async {
                if ready, let target = URL(string: "http://127.0.0.1:\(self.port)/") {
                    self.webView.load(URLRequest(url: target, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 30))
                } else {
                    self.showLoadingPage("The Studio backend did not start on port \(self.port).")
                }
            }
        }
    }

    func setupMenu() {
        let mainMenu = NSMenu()

        let appMenuItem = NSMenuItem()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "About OpenCore Studio", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(withTitle: "Hide OpenCore Studio", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        let hideOthers = NSMenuItem(title: "Hide Others", action: #selector(NSApplication.hideOtherApplications(_:)), keyEquivalent: "h")
        hideOthers.keyEquivalentModifierMask = [.command, .option]
        appMenu.addItem(hideOthers)
        appMenu.addItem(withTitle: "Show All", action: #selector(NSApplication.unhideAllApplications(_:)), keyEquivalent: "")
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(withTitle: "Quit OpenCore Studio", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appMenuItem.submenu = appMenu
        mainMenu.addItem(appMenuItem)

        let fileMenuItem = NSMenuItem()
        let fileMenu = NSMenu(title: "File")
        let loadItem = fileMenu.addItem(withTitle: "Load config.plist…", action: #selector(openConfigPlist), keyEquivalent: "o")
        loadItem.target = self
        let exportItem = fileMenu.addItem(withTitle: "Export config.plist…", action: #selector(exportConfigPlist), keyEquivalent: "s")
        exportItem.target = self
        fileMenuItem.submenu = fileMenu
        mainMenu.addItem(fileMenuItem)

        let ocMenuItem = NSMenuItem()
        let ocMenu = NSMenu(title: "OpenCore")
        let switchItem = ocMenu.addItem(withTitle: "Switch Version…", action: #selector(showOpenCoreVersions), keyEquivalent: "")
        switchItem.target = self
        ocMenuItem.submenu = ocMenu
        mainMenu.addItem(ocMenuItem)

        let editMenuItem = NSMenuItem()
        let editMenu = NSMenu(title: "Edit")
        editMenu.addItem(withTitle: "Undo", action: Selector(("undo:")), keyEquivalent: "z")
        editMenu.addItem(withTitle: "Redo", action: Selector(("redo:")), keyEquivalent: "Z")
        editMenu.addItem(NSMenuItem.separator())
        editMenu.addItem(withTitle: "Cut", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        editMenu.addItem(withTitle: "Copy", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        editMenu.addItem(withTitle: "Paste", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        editMenu.addItem(withTitle: "Select All", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editMenuItem.submenu = editMenu
        mainMenu.addItem(editMenuItem)

        let viewMenuItem = NSMenuItem()
        let viewMenu = NSMenu(title: "View")
        let reloadItem = viewMenu.addItem(withTitle: "Reload", action: #selector(reloadStudio), keyEquivalent: "r")
        reloadItem.target = self
        viewMenuItem.submenu = viewMenu
        mainMenu.addItem(viewMenuItem)

        let windowMenuItem = NSMenuItem()
        let windowMenu = NSMenu(title: "Window")
        windowMenu.addItem(withTitle: "Minimize", action: #selector(NSWindow.miniaturize(_:)), keyEquivalent: "m")
        windowMenu.addItem(withTitle: "Zoom", action: #selector(NSWindow.zoom(_:)), keyEquivalent: "")
        windowMenuItem.submenu = windowMenu
        mainMenu.addItem(windowMenuItem)
        NSApp.windowsMenu = windowMenu

        NSApp.mainMenu = mainMenu
    }

    func handleStudioMessage(_ body: Any) {
        let command = (body as? String) ?? ""
        if command == "loadPlist" {
            openConfigPlist()
        } else if command == "exportPlist" {
            exportConfigPlist()
        } else if command == "switchOpenCore" {
            showOpenCoreVersions()
        }
    }

    func supportFile(_ name: String) -> URL {
        let root = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("OpenCore Studio", isDirectory: true)
        try? FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        return root.appendingPathComponent(name)
    }

    func plistData(from url: URL) -> Data? {
        guard let data = try? Data(contentsOf: url) else { return nil }
        if let text = String(data: data, encoding: .utf8), text.contains("<plist") {
            return data
        }
        guard let plist = try? PropertyListSerialization.propertyList(from: data, options: [], format: nil),
              let xmlData = try? PropertyListSerialization.data(fromPropertyList: plist, format: .xml, options: 0) else {
            return data
        }
        return xmlData
    }

    @objc func openConfigPlist() {
        let panel = NSOpenPanel()
        panel.title = "Load config.plist"
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.allowsOtherFileTypes = true
        panel.allowedFileTypes = ["plist", "xml"]
        panel.begin { [weak self] response in
            guard response == .OK, let url = panel.url, let self = self else { return }
            guard let data = self.plistData(from: url) else { return }
            do {
                try data.write(to: self.supportFile("pending-import.plist"), options: .atomic)
            } catch {
                return
            }
            DispatchQueue.main.async {
                self.webView.evaluateJavaScript("window.ocsImportPendingNative && window.ocsImportPendingNative()", completionHandler: nil)
            }
        }
    }

    @objc func exportConfigPlist() {
        webView.evaluateJavaScript("window.ocsExportPlist && window.ocsExportPlist()", completionHandler: nil)
    }

    @objc func showOpenCoreVersions() {
        webView.evaluateJavaScript("window.ocsShowVersionPicker && window.ocsShowVersionPicker()", completionHandler: nil)
    }

    @objc func reloadStudio() {
        if let url = URL(string: "http://127.0.0.1:\(port)/") {
            webView.load(URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 30))
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window.makeKeyAndOrderFront(nil)
        return true
    }

    func applicationWillTerminate(_ notification: Notification) {
        if let proc = serverProcess, proc.isRunning {
            proc.terminate()
        }
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        if #available(macOS 11.3, *) {
            if let response = navigationResponse.response as? HTTPURLResponse {
                let disposition = response.value(forHTTPHeaderField: "Content-Disposition") ?? ""
                if disposition.localizedCaseInsensitiveContains("attachment") {
                    decisionHandler(.download)
                    return
                }
            }
        }
        decisionHandler(.allow)
    }

    @available(macOS 11.3, *)
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) {
        download.delegate = self
    }

    @available(macOS 11.3, *)
    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let panel = NSSavePanel()
        panel.canCreateDirectories = true
        panel.nameFieldStringValue = suggestedFilename
        panel.begin { result in
            completionHandler(result == .OK ? panel.url : nil)
        }
    }
}

let delegate = AppDelegate()
let app = NSApplication.shared
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
