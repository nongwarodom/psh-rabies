/**
 * Receiver for the PSH Rabies in-app survey form (หน้า "บันทึกสำรวจครัวเรือน").
 *
 * SETUP (one time) — see README section "📝 แบบบันทึกสำรวจครัวเรือน":
 *  1. Open the PRIVATE Google Sheet → Extensions → Apps Script → paste this whole file → Save.
 *  2. Project Settings (⚙️) → Script Properties → Add:  TOKEN = <same value as secrets [survey_apps_script] token>
 *  3. Deploy → New deployment → type "Web app" → Execute as: Me · Who has access: Anyone → Deploy
 *     → copy the Web app URL (…/exec) into secrets [survey_apps_script] url.
 *  UPDATING this code later: paste → Save → Deploy → Manage deployments → ✏️ Edit → Version: "New version"
 *     → Deploy (the URL stays the same).
 *
 * "Anyone" only means the app can call the URL; requests without the correct TOKEN are rejected,
 * and the sheet itself stays Restricted (share it only with staff).
 * No sheet ID or token is stored in this file (the repo is public).
 */
function doPost(e) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000); // serialise concurrent submissions
  try {
    var body = JSON.parse(e.postData.contents);
    var token = PropertiesService.getScriptProperties().getProperty('TOKEN');
    if (!token || body.token !== token) return json_({ ok: false, error: 'unauthorized' });

    var ss = SpreadsheetApp.getActiveSpreadsheet();
    if (body.action === 'read') return json_({ ok: true, tables: read_(ss, body.columns) });

    Object.keys(body.tables).forEach(function (name) {
      var t = body.tables[name];
      var sh = ss.getSheetByName(name) || ss.insertSheet(name);
      if (sh.getLastRow() === 0) {
        sh.appendRow(t.columns);
        sh.setFrozenRows(1);
        sh.getRange(1, 1, 1, t.columns.length).setFontWeight('bold');
      }
      if (t.rows.length) {
        var range = sh.getRange(sh.getLastRow() + 1, 1, t.rows.length, t.columns.length);
        range.setNumberFormat('@'); // plain text → keeps leading 0 of phone numbers / CID as typed
        range.setValues(t.rows);
      }
    });
    return json_({ ok: true });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}

/** For the dashboard: return ONLY the requested columns, never names / CID / phone numbers. */
var BLOCKED_ = ['first_name', 'last_name', 'cid', 'phone', 'owner_phone', 'surveyor'];

function read_(ss, columns) {
  var out = {};
  Object.keys(columns || {}).forEach(function (name) {
    var want = columns[name].filter(function (c) { return BLOCKED_.indexOf(c) < 0; });
    var sh = ss.getSheetByName(name);
    if (!sh || sh.getLastRow() < 2) { out[name] = { columns: want, rows: [] }; return; }
    var values = sh.getDataRange().getDisplayValues();
    var header = values[0];
    var idx = want.map(function (c) { return header.indexOf(c); });
    out[name] = {
      columns: want,
      rows: values.slice(1).map(function (r) { return idx.map(function (i) { return i < 0 ? '' : r[i]; }); }),
    };
  });
  return out;
}

function doGet() {
  return json_({ ok: true, service: 'psh-rabies-survey' }); // health check only, never returns data
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
