import Cocoa
import WebKit
import SQLite3

// ========== SQLite 数据库 ==========

var dbDir: URL {
    let dir = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Application Support/双色球")
    try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
    return dir
}
var dbPath: String { dbDir.appendingPathComponent("ssq.db").path }

func openDB() -> OpaquePointer? {
    var db: OpaquePointer?
    if sqlite3_open(dbPath, &db) != SQLITE_OK {
        print("Failed to open database: \(dbPath)")
        return nil
    }
    sqlite3_exec(db, "PRAGMA journal_mode=WAL", nil, nil, nil)
    return db
}

func initDB() {
    guard let db = openDB() else { return }
    let schema = """
        CREATE TABLE IF NOT EXISTS draws (
            period   INTEGER PRIMARY KEY,
            r1       INTEGER NOT NULL,
            r2       INTEGER NOT NULL,
            r3       INTEGER NOT NULL,
            r4       INTEGER NOT NULL,
            r5       INTEGER NOT NULL,
            r6       INTEGER NOT NULL,
            blue     INTEGER NOT NULL,
            source   TEXT    NOT NULL DEFAULT '中彩网',
            fetched_at TEXT  NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS user_picks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            period     INTEGER NOT NULL,
            r1         INTEGER NOT NULL,
            r2         INTEGER NOT NULL,
            r3         INTEGER NOT NULL,
            r4         INTEGER NOT NULL,
            r5         INTEGER NOT NULL,
            r6         INTEGER NOT NULL,
            blue       INTEGER NOT NULL,
            strategy   TEXT,
            score      INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
    """
    sqlite3_exec(db, schema, nil, nil, nil)
    sqlite3_close(db)
}

func dbLoadDraws(limit: Int? = nil) -> [[Int]] {
    guard let db = openDB() else { return [] }
    var sql = "SELECT period, r1, r2, r3, r4, r5, r6, blue FROM draws ORDER BY period"
    if let n = limit { sql += " LIMIT \(n)" }
    var stmt: OpaquePointer?
    var results = [[Int]]()
    if sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK {
        while sqlite3_step(stmt) == SQLITE_ROW {
            let period = Int(sqlite3_column_int(stmt, 0))
            let r = (1...7).map { Int(sqlite3_column_int(stmt, Int32($0))) }
            results.append([period] + r)
        }
    }
    sqlite3_finalize(stmt)
    sqlite3_close(db)
    return results
}

func dbUpsertDraws(_ rows: [[Int]], source: String) {
    guard let db = openDB() else { return }
    let sql = """
        INSERT OR REPLACE INTO draws (period, r1, r2, r3, r4, r5, r6, blue, source, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
    """
    var stmt: OpaquePointer?
    if sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK {
        for row in rows {
            sqlite3_bind_int(stmt, 1, Int32(row[0]))
            for i in 1...7 { sqlite3_bind_int(stmt, Int32(i + 1), Int32(row[i])) }
            sqlite3_bind_text(stmt, 9, (source as NSString).utf8String, -1, nil)
            sqlite3_step(stmt)
            sqlite3_reset(stmt)
        }
    }
    sqlite3_finalize(stmt)
    sqlite3_close(db)
}

func dbInsertUserPick(period: Int, reds: [Int], blue: Int, strategy: String, score: Int) {
    guard let db = openDB() else { return }
    let sql = """
        INSERT INTO user_picks (period, r1, r2, r3, r4, r5, r6, blue, strategy, score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    var stmt: OpaquePointer?
    if sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK {
        sqlite3_bind_int(stmt, 1, Int32(period))
        for i in 0..<6 { sqlite3_bind_int(stmt, Int32(i + 2), Int32(reds[i])) }
        sqlite3_bind_int(stmt, 8, Int32(blue))
        sqlite3_bind_text(stmt, 9, (strategy as NSString).utf8String, -1, nil)
        sqlite3_bind_int(stmt, 10, Int32(score))
        sqlite3_step(stmt)
    }
    sqlite3_finalize(stmt)
    sqlite3_close(db)
}

func dbSetLastFetchTime() {
    guard let db = openDB() else { return }
    let ts = String(Date().timeIntervalSince1970)
    sqlite3_exec(db, "INSERT OR REPLACE INTO meta (key, value) VALUES ('last_fetch_time', '\(ts)')", nil, nil, nil)
    sqlite3_close(db)
}

func dbLastFetchAge() -> TimeInterval {
    guard let db = openDB() else { return .infinity }
    var stmt: OpaquePointer?
    var age: TimeInterval = .infinity
    if sqlite3_prepare_v2(db, "SELECT value FROM meta WHERE key='last_fetch_time'", -1, &stmt, nil) == SQLITE_OK {
        if sqlite3_step(stmt) == SQLITE_ROW,
           let text = sqlite3_column_text(stmt, 0) {
            let ts = TimeInterval(String(cString: text)) ?? 0
            age = Date().timeIntervalSince1970 - ts
        }
    }
    sqlite3_finalize(stmt)
    sqlite3_close(db)
    return age
}

// ========== 数据拉取 ==========

func fetchSSQData(completion: @escaping (String, [[Int]]?, [[Int]]?) -> Void) {
    let url = URL(string: "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?name=ssq&issueCount=300")!
    var req = URLRequest(url: url, timeoutInterval: 20)
    req.setValue("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36", forHTTPHeaderField: "User-Agent")
    req.setValue("https://www.cwl.gov.cn/ygkj/ssq/kjgg/", forHTTPHeaderField: "Referer")
    req.setValue("application/json, text/plain, */*", forHTTPHeaderField: "Accept")
    req.setValue("zh-CN,zh;q=0.9,en;q=0.8", forHTTPHeaderField: "Accept-Language")

    let config = URLSessionConfiguration.default
    config.httpCookieStorage = HTTPCookieStorage.shared
    config.httpShouldSetCookies = true
    let session = URLSession(configuration: config)

    session.dataTask(with: req) { data, _, error in
        guard let data = data, error == nil,
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            completion("中彩网请求失败", nil, nil)
            return
        }
        var items = (json["result"] as? [[String: Any]]) ?? (json["data"] as? [[String: Any]]) ?? []
        if let dict = json["result"] as? [String: Any] {
            items = (dict["list"] as? [[String: Any]]) ?? (dict["records"] as? [[String: Any]]) ?? []
        }
        var results = [[Int]]()
        for item in items {
            let code = item["code"] as? String ?? item["drawNum"] as? String ?? ""
            let redStr = item["red"] as? String ?? ""
            let blueStr = item["blue"] as? String ?? ""
            guard code.hasPrefix("20"), redStr != "" else { continue }
            let reds = redStr.components(separatedBy: CharacterSet(charactersIn: "|, ")).compactMap { Int($0) }
            let blues = blueStr.components(separatedBy: CharacterSet(charactersIn: "|, ")).compactMap { Int($0) }
            if reds.count == 6, let blue = blues.first, let period = Int(code) {
                results.append([period] + reds + [blue])
            }
        }
        results.sort { $0[0] < $1[0] }

        if !results.isEmpty {
            dbUpsertDraws(results, source: "中彩网")
            dbSetLastFetchTime()
        }

        let longData = results
        let shortData = Array(results.suffix(100))
        completion(results.isEmpty ? "未解析到数据" : "中彩网",
                   shortData.isEmpty ? nil : shortData,
                   longData.count > 100 ? longData : nil)
    }.resume()
}

// ========== UI ==========

class AppDelegate: NSObject, NSApplicationDelegate, WKScriptMessageHandler {
    var window: NSWindow!
    var webView: WKWebView!

    func userContentController(_ uc: WKUserContentController, didReceive msg: WKScriptMessage) {
        if msg.name == "save" {
            if let body = msg.body as? String,
               let json = try? JSONSerialization.jsonObject(with: body.data(using: .utf8)!) as? [String: Any],
               let picks = json["picks"] as? [[String: Any]] {
                for p in picks {
                    if let period = p["period"] as? Int,
                       let reds = p["reds"] as? [Int],
                       let blue = p["blue"] as? Int {
                        dbInsertUserPick(
                            period: period, reds: reds, blue: blue,
                            strategy: p["strategy"] as? String ?? "",
                            score: p["score"] as? Int ?? 0
                        )
                    }
                }
            }
            return
        }
        if msg.name == "fetch" {
            fetchSSQData { source, shortData, longData in
                let json: String
                if let d = shortData {
                    let jsonData = (try? JSONSerialization.data(withJSONObject: d)) ?? Data()
                    let dataStr = String(data: jsonData, encoding: .utf8) ?? "[]"

                    var longStr = "null"
                    if let ld = longData {
                        let ldJson = (try? JSONSerialization.data(withJSONObject: ld)) ?? Data()
                        longStr = String(data: ldJson, encoding: .utf8) ?? "null"
                    }

                    json = "{\"ok\":true,\"source\":\"\(source)\",\"count\":\(d.count),\"data\":\(dataStr),\"longData\":\(longStr)}"
                } else {
                    json = "{\"ok\":false,\"msg\":\"\(source)\"}"
                }
                DispatchQueue.main.async {
                    self.webView.evaluateJavaScript("onFetchResult(\(json))", completionHandler: nil)
                }
            }
        }
    }

    func applicationDidFinishLaunching(_ n: Notification) {
        initDB()

        let config = WKWebViewConfiguration()
        config.userContentController.add(self, name: "fetch")
        config.userContentController.add(self, name: "save")

        webView = WKWebView(frame: .zero, configuration: config)
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 760, height: 720),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "双色球 · SQLite 版"
        window.center()
        window.contentView = webView
        window.makeKeyAndOrderFront(nil)

        // Load HTML from filesystem
        var html = ""
        let bundledPath = Bundle.main.path(forResource: "index", ofType: "html") ?? ""
        let siblingPath = Bundle.main.bundleURL.deletingLastPathComponent().appendingPathComponent("index.html").path
        let cwdPath = FileManager.default.currentDirectoryPath + "/index.html"
        for p in [bundledPath, siblingPath, cwdPath] {
            if !p.isEmpty, let content = try? String(contentsOfFile: p, encoding: .utf8), !content.isEmpty {
                html = content; break
            }
        }
        if html.isEmpty {
            html = "<html><body style='font-family:sans-serif;padding:40px;text-align:center'><h2>无法加载 index.html</h2><p>请将 index.html 放在应用同目录下</p></body></html>"
        }
        let base = Bundle.main.resourceURL?.absoluteString ?? "about:blank"
        webView.loadHTMLString(html, baseURL: URL(string: base))

        // 启动后自动加载数据库中的数据
        let saved = dbLoadDraws(limit: 100)
        if !saved.isEmpty {
            let jsonStr = (try? JSONSerialization.data(withJSONObject: saved)) ?? Data()
            let dataStr = String(data: jsonStr, encoding: .utf8) ?? "[]"

            let allData = dbLoadDraws()
            var longStr = "null"
            if allData.count > saved.count {
                let ldJson = (try? JSONSerialization.data(withJSONObject: allData)) ?? Data()
                longStr = String(data: ldJson, encoding: .utf8) ?? "null"
            }

            let js = "if(typeof onFetchResult==='function'){onFetchResult({\"ok\":true,\"source\":\"本地数据库\",\"count\":\(saved.count),\"data\":\(dataStr),\"longData\":\(longStr)})}"
            webView.evaluateJavaScript(js, completionHandler: nil)
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_: NSApplication) -> Bool { true }
}

// ========== 入口 ==========

let app = NSApplication.shared
let dlg = AppDelegate()
app.delegate = dlg
app.setActivationPolicy(.regular)
app.run()
