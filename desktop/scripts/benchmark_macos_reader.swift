import AppKit
import WebKit

final class ReaderProbe: NSObject, NSApplicationDelegate, WKNavigationDelegate {
    private let url: URL
    private let script: String
    private let webView: WKWebView
    private let panel: NSPanel
    private var started = false
    private let activity = ProcessInfo.processInfo.beginActivity(
        options: [.userInitiated, .latencyCritical], reason: "Synthetic reader benchmark")

    init(url: URL, script: String) {
        self.url = url
        self.script = script
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        let frame = NSRect(x: 40, y: 40, width: 1200, height: 780)
        webView = WKWebView(frame: frame, configuration: configuration)
        panel = NSPanel(contentRect: frame, styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        panel.contentView = webView
        panel.ignoresMouseEvents = true
        panel.alphaValue = 0.03
        panel.level = .floating
        panel.orderFrontRegardless()
        webView.navigationDelegate = self
        webView.load(URLRequest(url: url))
        DispatchQueue.main.asyncAfter(deadline: .now() + 60) {
            fail("Reader probe did not complete within 60 seconds")
        }
    }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        let destination = action.request.url
        let allowed = destination?.scheme == "http" && destination?.host == "127.0.0.1" && destination?.port == url.port
        decisionHandler(allowed ? .allow : .cancel)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        guard !started else { return }
        started = true
        webView.callAsyncJavaScript(script + "\nreturn await benchmarkReader();", arguments: [:], in: nil, in: .page) { result in
            switch result {
            case .success(let value):
                guard let report = value as? String else { fail("Reader probe returned no report") }
                print(report)
                exit(0)
            case .failure(let error):
                let reason = (error as NSError).userInfo["WKJavaScriptExceptionMessage"] as? String
                fail(reason ?? "Reader benchmark JavaScript failed")
            }
        }
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        fail("Reader navigation failed with code \((error as NSError).code)")
    }
}

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}

guard CommandLine.arguments.count == 2, let address = readLine(), let url = URL(string: address),
      url.scheme == "http", url.host == "127.0.0.1", url.port != nil else {
    fail("Expected a local reader URL on stdin and the benchmark script path as an argument")
}
let script = try String(contentsOfFile: CommandLine.arguments[1], encoding: .utf8)
let delegate = ReaderProbe(url: url, script: script)
let application = NSApplication.shared
application.setActivationPolicy(.accessory)
application.delegate = delegate
application.run()
