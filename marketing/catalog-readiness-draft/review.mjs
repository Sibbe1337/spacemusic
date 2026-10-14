import { economics, planningAssumptions } from "./model.mjs";
const money = (v) =>
  new Intl.NumberFormat("sv-SE", { style: "currency", currency: "EUR" }).format(
    v,
  );
const inputs = Object.keys(planningAssumptions).map((key) =>
  document.getElementById(key),
);
const ids = [
  "revenue",
  "fees",
  "reserve",
  "labor",
  "otherCostResult",
  "contribution",
];
function update() {
  const values = {};
  let invalid = false;
  for (const input of inputs) {
    const valid =
      input.value.trim() !== "" &&
      input.validity.valid &&
      Number.isFinite(input.valueAsNumber);
    input.setAttribute("aria-invalid", String(!valid));
    invalid ||= !valid;
    values[input.name] = input.valueAsNumber;
  }
  try {
    if (invalid) throw new Error("Incomplete inputs");
    const result = economics(values);
    for (const id of ids)
      document.getElementById(id).textContent = money(
        result[id === "otherCostResult" ? "otherCost" : id],
      );
    document.getElementById("cost-error").textContent = "";
    document.getElementById("result-note").textContent =
      `Vid ${values.minutes} minuters arbete. ${result.contribution < 0 ? "Modellen visar ett negativt bidrag." : "Inte vinst efter alla bolagskostnader."}`;
    document.getElementById("break-even").textContent =
      result.breakEvenState === "unreachable"
        ? "Priset täcker inte övriga kostnader, även med noll minuters arbete."
        : result.breakEvenState === "no-hourly-cost"
          ? "Noll arbetskostnad: tidsutrymme kan inte beräknas."
          : result.breakEvenMinutes === 0
            ? "Inget tidsutrymme: kostnader före arbete motsvarar hela intäkten."
            : `Utrymme för cirka ${Math.floor(result.breakEvenMinutes)} minuters arbete före nollbidrag.`;
  } catch {
    document.getElementById("cost-error").textContent =
      "Fyll i giltiga, icke-negativa tal i alla fält. Procentsatser måste vara 0–100.";
    for (const id of ids)
      document.getElementById(id).textContent = "Ej beräknat";
    document.getElementById("result-note").textContent =
      "Ingen kalkyl visas förrän alla ingångsvärden är giltiga.";
    document.getElementById("break-even").textContent = "";
  }
}
for (const input of inputs) input.addEventListener("input", update);
update();
