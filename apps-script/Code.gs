/**
 * Morning Companion — Apps Script webhook.
 * Receives push subscriptions from the PWA and stores them in the `push` tab.
 *
 * push tab columns: user_id | subscription_json | created_utc | last_reminder_utc | token
 *
 * Validation rules:
 *  - user_id must look like U###               -> bad_id
 *  - user_id must exist in the users tab        -> unknown_user
 *  - one push endpoint = one participant        -> endpoint_taken
 *    (a device/browser cannot register someone else's ID)
 *
 * Deploy: Extensions → Apps Script → Deploy → New deployment → Web app
 *   - Execute as: Me
 *   - Who has access: Anyone
 * After ANY code change: Deploy → Manage deployments → edit → New version.
 */

const SHEET_ID = "17GfHPSW6CBb67IqSz7zxQ82dozlO5Xq2bGxaXMdKT2w";   

function doPost(e) {
  const out = ContentService.createTextOutput();
  try {
    const data = JSON.parse(e.postData.contents);
    const uid = String(data.user_id || "").trim().toUpperCase();
    const token = String(data.token || "").trim();
    const sub = data.subscription;

    if (!/^U\d{3}$/.test(uid)) {
      return out.setContent(JSON.stringify({ ok: false, error: "bad_id" }));
    }
    if (!sub || !sub.endpoint) {
      return out.setContent(JSON.stringify({ ok: false, error: "bad_subscription" }));
    }

    const doc = SpreadsheetApp.openById(SHEET_ID);

    // user must exist
    const usersSheet = doc.getSheetByName("users");
    const users = usersSheet.getDataRange().getValues().map(r => String(r[0]));
    if (users.indexOf(uid) === -1) {
      return out.setContent(JSON.stringify({ ok: false, error: "unknown_user" }));
    }

    // one endpoint = one ID: reject if this browser already registered another ID
    const pushSheet = doc.getSheetByName("push");
    const rows = pushSheet.getDataRange().getValues();
    for (let i = 1; i < rows.length; i++) {
      try {
        const existing = JSON.parse(rows[i][1]);
        if (existing.endpoint === sub.endpoint && String(rows[i][0]) !== uid) {
          return out.setContent(JSON.stringify({ ok: false, error: "endpoint_taken" }));
        }
      } catch (err) { /* ignore malformed rows */ }
    }

    // update in place if this endpoint already belongs to this user
    const now = new Date().toISOString();
    for (let i = 1; i < rows.length; i++) {
      try {
        const existing = JSON.parse(rows[i][1]);
        if (existing.endpoint === sub.endpoint && String(rows[i][0]) === uid) {
          pushSheet.getRange(i + 1, 2).setValue(JSON.stringify(sub));
          if (token) pushSheet.getRange(i + 1, 5).setValue(token);
          return out.setContent(JSON.stringify({ ok: true, updated: true }));
        }
      } catch (err) { /* ignore malformed rows */ }
    }

    pushSheet.appendRow([uid, JSON.stringify(sub), now, "", token]);
    return out.setContent(JSON.stringify({ ok: true }));
  } catch (err) {
    return out.setContent(JSON.stringify({ ok: false, error: String(err) }));
  }
}
