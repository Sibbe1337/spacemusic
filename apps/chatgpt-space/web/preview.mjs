import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { AppBridge, PostMessageTransport } from '@modelcontextprotocol/ext-apps/app-bridge';

const iframe = document.querySelector('#widget');
const theme = document.querySelector('#theme');
const error = document.querySelector('#preview-error');
const client = new Client({ name: 'space-local-preview-host', version: '0.1.0' });
const report = () => { error.textContent = 'The local preview could not connect. Check that the server is running, then reload this page.'; };
try {
  await client.connect(new StreamableHTTPClientTransport(new URL('/mcp', location.origin)), { timeout: 8000 });
  const bridge = new AppBridge(null, { name: 'SPACE local host simulation', version: '0.1.0' }, { serverTools: {} },
    { hostContext: { theme: theme.value, displayMode: 'inline', availableDisplayModes: ['inline'], locale: 'en-GB' } });
  bridge.oncalltool = params => client.callTool(params, undefined, { timeout: 8000 });
  bridge.onsizechange = ({ height }) => {
    if (Number.isFinite(height)) iframe.style.height = `${Math.min(6000, Math.max(300, height))}px`;
  };
  bridge.oninitialized = async () => {
    try {
      await bridge.sendToolInput({ arguments: {} });
      await bridge.sendToolResult(await client.callTool({ name: 'space_list_demo_catalogs', arguments: {} }));
    } catch { report(); }
  };
  await bridge.connect(new PostMessageTransport(iframe.contentWindow, iframe.contentWindow));
  theme.addEventListener('change', () => bridge.setHostContext({ theme: theme.value, displayMode: 'inline', availableDisplayModes: ['inline'], locale: 'en-GB' }));
  iframe.src = '/widget.html';
  window.addEventListener('pagehide', () => { void bridge.close(); void client.close(); }, { once: true });
} catch { report(); }
