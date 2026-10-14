import { mountDealflow } from "/dealflow/dealflow.mjs";
import { createClient } from "/dealflow/client.mjs";

let app;
const role = document.querySelector("#demo-role");
function start() {
  app?.destroy();
  const selected = role.value;
  const client = createClient({
    fetchImpl: (url, options) =>
      fetch(url, {
        ...options,
        headers: { ...options.headers, "X-Demo-Role": selected },
      }),
  });
  app = mountDealflow({ client });
  app.load({ discard: true });
}
role.addEventListener("change", start);
start();
