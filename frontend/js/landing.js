// Landing page behaviour: scroll reveal, header shadow, gentle pointer parallax on the hero art, and a
// clickable example of the assistant's approval card (it demonstrates the rule that nothing changes until
// the customer approves). No data leaves the page.
import { api } from "./api.js";
import { announce } from "./lib/announce.js";
import { fill, h } from "./lib/dom.js";
import { fmtMoney } from "./lib/format.js";
import { confetti, reduced, reveal, tweenNumber } from "./lib/motion.js";

// Scroll reveal, with a small stagger inside groups.
document.querySelectorAll(".occasions li, .steps li").forEach((el, i) => el.style.setProperty("--i", i % 6));
reveal(document.querySelectorAll(".reveal"));

// Header gets a shadow once the page has scrolled.
const header = document.querySelector(".top");
if (header && "IntersectionObserver" in window) {
  const sentinel = document.createElement("span");
  sentinel.setAttribute("aria-hidden", "true");
  sentinel.style.cssText = "position:absolute;top:0;left:0;width:1px;height:1px;pointer-events:none";
  document.body.prepend(sentinel);
  new IntersectionObserver(([entry]) => header.classList.toggle("is-stuck", !entry.isIntersecting)).observe(sentinel);
}

// Hero art drifts a few pixels toward the pointer. Fine pointers only; never when motion is reduced.
const art = document.querySelector(".hero-art");
if (art && matchMedia("(pointer: fine)").matches && !reduced()) {
  let frame = 0;
  document.querySelector(".hero")?.addEventListener("pointermove", (e) => {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      const r = art.getBoundingClientRect();
      art.style.setProperty("--px", ((e.clientX - r.left) / r.width - 0.5).toFixed(3));
      art.style.setProperty("--py", ((e.clientY - r.top) / r.height - 0.5).toFixed(3));
    });
  });
  document.querySelector(".hero")?.addEventListener("pointerleave", () => {
    art.style.setProperty("--px", "0");
    art.style.setProperty("--py", "0");
  });
}

// Example proposal: approve, reject, or start over.
const demo = document.getElementById("demo-proposal");
if (demo) {
  const $ = (id) => document.getElementById(id);
  const actions = $("demo-actions");
  const done = $("demo-done");
  const note = $("demo-note");
  const totalLine = $("demo-total");
  const totalNum = $("demo-total-n");
  const avatar = $("demo-avatar");
  const BEFORE = 1200;
  const AFTER = 1350;

  const settle = (applied) => {
    actions.hidden = true;
    done.hidden = false;
    totalLine.hidden = false;
    avatar.hidden = !applied;
    demo.classList.toggle("is-applied", applied);
    demo.classList.toggle("is-rejected", !applied);
    note.className = `badge ${applied ? "badge-green" : ""}`;
    note.textContent = applied ? "השינוי הוחל בהזמנה" : "השינוי נדחה. ההזמנה נשארה כמו שהייתה.";
    tweenNumber(totalNum, BEFORE, applied ? AFTER : BEFORE, fmtMoney);
    if (applied) confetti(avatar);
    $("demo-reset").focus();
  };

  $("demo-approve").addEventListener("click", () => settle(true));
  $("demo-reject").addEventListener("click", () => settle(false));
  $("demo-reset").addEventListener("click", () => {
    demo.classList.remove("is-applied", "is-rejected");
    done.hidden = true;
    totalLine.hidden = true;
    actions.hidden = false;
    $("demo-approve").focus();
  });
}

// Lead form. The server validates and scores; the browser only collects and shows the result.
const leadRoot = document.getElementById("lead-root");
if (leadRoot) {
  const EVENT_TYPES = ["יום הולדת", "אירוע משפחתי", "בר או בת מצווה", "ארוחת שבת", "יום נישואין", "חגיגה פרטית", "אחר"];
  const BUDGETS = [["low", "חסכוני"], ["mid", "בינוני"], ["high", "גבוה"], ["premium", "פרימיום"]];
  const params = new URLSearchParams(location.search);
  const source = ["utm_source", "utm_medium", "utm_campaign"].map((k) => params.get(k)).filter(Boolean).join("_").slice(0, 100);
  const tomorrow = new Date(Date.now() + 864e5 - new Date().getTimezoneOffset() * 6e4).toISOString().slice(0, 10);

  // Required fields say so in the label text (WCAG 3.3.2), same pattern as the customer app.
  const field = (id, labelText, control, { required = false, hint } = {}) => {
    control.id = id;
    control.classList.add("input");
    if (required) control.required = true;
    const hintId = `${id}-hint`;
    if (hint) control.setAttribute("aria-describedby", hintId);
    return h("div", { class: "field" },
      h("label", { for: id }, labelText, h("span", { class: "req", text: required ? " (חובה)" : " (אופציונלי)" })),
      control,
      hint ? h("p", { class: "hint", id: hintId, text: hint }) : null);
  };

  const name = h("input", { type: "text", name: "full_name", autocomplete: "name", minlength: "2", maxlength: "80" });
  const phone = h("input", { type: "tel", name: "phone", autocomplete: "tel", inputmode: "tel", dir: "ltr" });
  const email = h("input", { type: "email", name: "email", autocomplete: "email", dir: "ltr", maxlength: "254" });
  const type = h("select", { name: "event_type" }, EVENT_TYPES.map((t) => h("option", { value: t, text: t })));
  const date = h("input", { type: "date", name: "event_date", min: tomorrow });
  const guests = h("input", { type: "number", name: "guests", min: "1", max: "5000", inputmode: "numeric" });
  const budget = h("select", { name: "budget_band" }, BUDGETS.map(([v, t]) => h("option", { value: v, text: t })));
  const message = h("textarea", { name: "message", rows: "3", maxlength: "1000" });
  // Honeypot: hidden from people and from assistive tech. Bots that fill every input get rejected.
  const trap = h("input", { type: "text", name: "website", tabindex: "-1", autocomplete: "off" });
  const consent = h("input", { type: "checkbox", id: "lead-consent", required: true });
  const submit = h("button", { class: "btn btn-primary", type: "submit" }, "שליחה");
  const status = h("p", { class: "lead-status", "aria-live": "polite", role: "status" });

  const form = h("form", { class: "lead-form stack-lg", onsubmit: async (e) => {
    e.preventDefault();
    submit.disabled = true;
    status.className = "lead-status";
    status.textContent = "שולחים...";
    try {
      await api("/api/leads", { method: "POST", body: JSON.stringify({
        full_name: name.value, phone: phone.value, email: email.value || null, event_type: type.value,
        event_date: date.value, guests: Number(guests.value), budget_band: budget.value,
        source: source || null, message: message.value || null, consent: consent.checked, website: trap.value,
      }) });
      fill(leadRoot, h("p", { class: "lead-status lead-ok", "aria-live": "polite", role: "status", text: "תודה! קיבלנו את הפרטים ונחזור אליכם בקרוב." }));
      announce("הפרטים נשלחו בהצלחה");
    } catch (err) {
      status.className = "lead-status lead-fail";
      status.textContent = err.status === 422 ? "בדקו שהפרטים תקינים (טלפון ישראלי, תאריך עתידי) ונסו שוב."
        : err.status === 429 ? "נשלחו יותר מדי פניות. נסו שוב בעוד כמה דקות."
        : "לא הצלחנו לשלוח כרגע. נסו שוב מאוחר יותר.";
      submit.disabled = false;
    }
  } },
    h("p", { class: "hint", text: "שדות שמסומנים ב״(חובה)״ צריך למלא כדי לשלוח." }),
    h("div", { class: "lead-grid" },
      field("lead-name", "שם מלא", name, { required: true }),
      field("lead-phone", "טלפון", phone, { required: true, hint: "למשל 050-1234567" }),
      field("lead-email", "אימייל", email),
      field("lead-type", "סוג האירוע", type, { required: true }),
      field("lead-date", "תאריך האירוע", date, { required: true }),
      field("lead-guests", "מספר אורחים", guests, { required: true }),
      field("lead-budget", "תקציב", budget, { required: true })),
    field("lead-message", "הודעה", message),
    h("div", { class: "lead-trap", "aria-hidden": "true" }, h("label", { for: "lead-website", text: "אל תמלאו את השדה הזה" }), Object.assign(trap, { id: "lead-website" })),
    h("label", { class: "lead-consent", for: "lead-consent" }, consent,
      h("span", {}, "אני מסכים/ה שיצרו איתי קשר בנוגע לפנייה זו", h("span", { class: "req", text: " (חובה)" }))),
    h("div", { class: "lead-actions" }, submit, status));
  fill(leadRoot, form);
}
