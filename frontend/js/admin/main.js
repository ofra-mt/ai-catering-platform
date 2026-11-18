// Owner dashboard: live quotation requests and dish management. RLS enforces the admin role.
import { announce } from "../lib/announce.js";
import { fill, h } from "../lib/dom.js";
import { fmtDate, fmtMoney } from "../lib/format.js";
import { dishImageUrl, isAdmin, requireSession, sb, signOut } from "../lib/supabase.js";

const root = document.getElementById("admin");
const session = await requireSession();

const STATUS = {
  draft: ["badge-pareve", "טיוטה"],
  pending_approval: ["badge-warning", "ממתין להחלטה"],
  approved: ["badge-green", "אושר"],
  rejected: ["badge-danger", "נדחה"],
};

const LEAD_STATUS = { new: "חדש", contacted: "נוצר קשר", quoted: "נשלחה הצעה", won: "נסגר", lost: "אבד" };
// Score bands: hot at 0.6 and above, warm at 0.35 and above. Text label always shown, not colour alone.
const leadBand = (score) => (score >= 0.6 ? ["badge-green", "חם"] : score >= 0.35 ? ["badge-warning", "פושר"] : ["badge-pareve", "קר"]);

const head = h("header", { class: "admin-head" },
  h("h1", { class: "auth-title", text: "ממשק העסק" }),
  h("button", { class: "btn btn-ghost", type: "button", onclick: signOut }, "יציאה"));

if (!isAdmin(session)) {
  fill(root, head, h("p", { role: "alert", text: "לחשבון הזה אין הרשאת ניהול." }));
} else {
  const leadsBox = h("ul", { class: "admin-list" });
  const ordersBox = h("ul", { class: "admin-list" });
  const dishesBox = h("ul", { class: "admin-list" });
  const message = h("p", { class: "error", role: "alert", hidden: true });

  const showError = (text) => {
    message.textContent = text;
    message.hidden = !text;
  };

  fill(root, head, message,
    h("section", { class: "stack", "aria-labelledby": "leads-title" },
      h("h2", { id: "leads-title", text: "לידים" }),
      h("p", { class: "muted small", text: "הציון הוא הערכה ראשונית (נתונים סינתטיים): הסיכוי שהליד יהפוך להזמנה." }),
      leadsBox),
    h("section", { class: "stack", "aria-labelledby": "orders-title" },
      h("h2", { id: "orders-title", text: "בקשות להצעת מחיר" }), ordersBox),
    h("section", { class: "stack", "aria-labelledby": "dishes-title" },
      h("h2", { id: "dishes-title", text: "מנות ותמונות" }), dishesBox));

  async function decide(orderId, decision, note) {
    showError("");
    const { error } = await sb.rpc("decide_order", { order_id: orderId, decision, note });
    if (error) showError(error.message);
  }

  function orderCard(o) {
    const [badge, label] = STATUS[o.status];
    const note = h("textarea", { class: "input", rows: 2, "aria-label": "הערה ללקוח" });
    return h("li", { class: "panel admin-order" },
      h("div", { class: "admin-order-head" },
        h("strong", { text: `${o.events.customers.full_name}, ${o.events.event_type}` }),
        h("span", { class: `badge ${badge}`, text: label })),
      h("p", { class: "muted", text: `${fmtDate(o.events.event_date)}, ${o.events.adults + o.events.children} אורחים, ${o.fulfillment_type === "delivery" ? `משלוח ל${o.delivery_address}` : "איסוף עצמי"}` }),
      h("p", { class: "muted small", text: o.order_items.map((i) => `${i.snapshot_name} × ${i.quantity}`).join(", ") }),
      h("strong", { class: "num", text: `סה״כ ${fmtMoney(o.total ?? 0)}` }),
      o.decision_note ? h("p", { class: "small", text: `הערה: ${o.decision_note}` }) : null,
      o.status === "pending_approval"
        ? [note, h("div", { class: "admin-actions" },
          h("button", { class: "btn btn-primary", type: "button", onclick: () => decide(o.id, "approved", note.value) }, "אישור"),
          h("button", { class: "btn btn-danger", type: "button", onclick: () => decide(o.id, "rejected", note.value) }, "דחייה"))]
        : null);
  }

  async function setLeadStatus(id, status) {
    showError("");
    const { error } = await sb.from("leads").update({ status }).eq("id", id);
    if (error) showError("עדכון הסטטוס נכשל. נסו שוב.");
  }

  function leadCard(l) {
    const pct = Math.round((l.score ?? 0) * 100);
    const [badge, band] = leadBand(l.score ?? 0);
    const selectId = `lead-status-${l.id}`;
    return h("li", { class: "panel admin-order" },
      h("div", { class: "admin-order-head" },
        h("strong", { text: `${l.full_name}, ${l.event_type}` }),
        h("span", { class: `badge ${badge}`, text: `${band} ${pct}%` })),
      h("p", { class: "muted", text: `${fmtDate(l.event_date)}, ${l.guests} אורחים` }),
      h("p", { class: "muted small", dir: "auto", text: [l.phone, l.email].filter(Boolean).join(" | ") }),
      h("p", { class: "small", text: `סיבות: ${(l.score_reasons ?? []).map((r) => `${r.direction} ${r.label}`).join(", ")}` }),
      h("div", { class: "field" },
        h("label", { for: selectId, text: "סטטוס" }),
        h("select", { id: selectId, class: "input", onchange: (e) => setLeadStatus(l.id, e.target.value) },
          Object.entries(LEAD_STATUS).map(([value, text]) => h("option", { value, text, selected: l.status === value })))));
  }

  async function loadLeads() {
    const { data, error } = await sb.from("leads")
      .select("id,full_name,phone,email,event_type,event_date,guests,status,score,score_reasons")
      .order("score", { ascending: false });
    if (error) return showError("לא הצלחנו לטעון את הלידים.");
    fill(leadsBox, data.length ? data.map(leadCard) : h("li", { class: "muted", text: "אין עדיין לידים." }));
  }

  async function updateDish(id, patch) {
    showError("");
    const { error } = await sb.from("dishes").update(patch).eq("id", id);
    if (error) showError("העדכון נכשל. נסו שוב.");
  }

  async function uploadImage(dish, file) {
    if (!file) return;
    showError("");
    const ext = file.name.split(".").pop().toLowerCase();
    const path = `${dish.id}/${crypto.randomUUID()}.${ext}`;
    const bucket = sb.storage.from("dish-images");
    const { error } = await bucket.upload(path, file, { contentType: file.type });
    if (error) return showError("העלאת התמונה נכשלה. אפשר להעלות JPG, PNG או WebP עד 5MB.");
    await updateDish(dish.id, { image_path: path });
    if (dish.image_path) await bucket.remove([dish.image_path]);
  }

  function dishRow(d) {
    const src = dishImageUrl(d.image_path);
    return h("li", { class: "panel admin-dish" },
      src ? h("img", { class: "admin-thumb", src, alt: "" }) : h("div", { class: "admin-thumb", "aria-hidden": "true" }),
      h("strong", { text: d.name }),
      h("span", { class: "num", text: fmtMoney(d.unit_price) }),
      h("div", { class: "admin-dish-controls" },
        h("div", { class: "field" },
          h("label", { for: `price-${d.id}`, text: "מחיר" }),
          h("input", { id: `price-${d.id}`, class: "input", type: "number", min: "0", step: "0.01", value: String(d.unit_price),
            onchange: (e) => (Number(e.target.value) >= 0 ? updateDish(d.id, { unit_price: Number(e.target.value) }) : showError("המחיר לא יכול להיות שלילי.")) })),
        h("label", { class: "admin-check" },
          h("input", { type: "checkbox", checked: d.is_available, onchange: (e) => updateDish(d.id, { is_available: e.target.checked }) }),
          "זמינה להזמנה"),
        h("div", { class: "field" },
          h("label", { for: `image-${d.id}`, text: "תמונה" }),
          h("input", { id: `image-${d.id}`, type: "file", accept: "image/jpeg,image/png,image/webp",
            onchange: (e) => uploadImage(d, e.target.files[0]) }))));
  }

  async function loadOrders() {
    const { data, error } = await sb.from("orders")
      .select("id,status,total,fulfillment_type,delivery_address,decision_note,submitted_at,order_items(snapshot_name,quantity),events(event_type,event_date,adults,children,customers(full_name))")
      .order("submitted_at", { ascending: false });
    if (error) return showError("לא הצלחנו לטעון את הבקשות.");
    fill(ordersBox, data.length ? data.map(orderCard) : h("li", { class: "muted", text: "אין עדיין בקשות." }));
  }

  async function loadDishes() {
    const { data, error } = await sb.from("dishes").select("id,name,unit_price,is_available,image_path").order("name");
    if (error) return showError("לא הצלחנו לטעון את המנות.");
    fill(dishesBox, data.map(dishRow));
  }

  await Promise.all([loadLeads(), loadOrders(), loadDishes()]);

  sb.channel("admin")
    .on("postgres_changes", { event: "*", schema: "public", table: "orders" }, () => {
      loadOrders();
      announce("רשימת הבקשות עודכנה");
    })
    .on("postgres_changes", { event: "*", schema: "public", table: "dishes" }, loadDishes)
    .subscribe();
}
