import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { registerAppResource, registerAppTool, RESOURCE_MIME_TYPE } from '@modelcontextprotocol/ext-apps/server';
import { noInputSchema, caseInputSchema, snapshotSchema } from '../shared/contract.mjs';
import { snapshot, toolResult } from './domain.mjs';

export const WIDGET_URI = 'ui://space/catalog-desk/v1.html';
export const tools = [
  { name: 'space_list_demo_catalogs', title: 'Explore SPACE demo catalogs', view: 'overview', schema: noInputSchema,
    description: 'Use this when the user wants to explore the SPACE Catalog Desk demo or find its three fictional catalog IDs. Synthetic examples only; cannot access real accounts, documents or leads.' },
  { name: 'space_review_demo_catalog', title: 'Review a fictional catalog', view: 'review', schema: caseInputSchema,
    description: 'Use this when the user wants missing evidence, review steps or source references for a SPACE demo catalog. Use a case_id from space_list_demo_catalogs. Document presence is not verified ownership or value. Does not accept files or real customer details.' },
  { name: 'space_compare_demo_buyers', title: 'Compare fictional buyer criteria', view: 'buyers', schema: caseInputSchema,
    description: 'Use this when the user wants to compare a SPACE demo catalog against three fictional buyer profiles and understand blockers. Not real buyers, a valuation, a financial recommendation or permission to share. No outreach or transaction is possible.' },
];

export function createMcpServer(widgetHtml) {
  const server = new McpServer({ name: 'space-catalog-desk-demo', version: '0.1.0' }, {
    instructions: 'This is a synthetic-only SPACE demo. Label all catalogs, figures, document statuses and buyers as fictional. Supplied documents are not verified rights or income. Never present a match as an offer, imply sharing occurred, or request real documents or personal data. Tools only accept the listed demo IDs.',
  });
  registerAppResource(server, 'SPACE Catalog Desk demo', WIDGET_URI, {}, async () => ({
    contents: [{ uri: WIDGET_URI, mimeType: RESOURCE_MIME_TYPE, text: widgetHtml,
      _meta: {
        ui: { prefersBorder: true, csp: { connectDomains: [], resourceDomains: [] } },
        'openai/widgetDescription': 'Read-only SPACE demo: fictional catalogs, evidence gaps and buyer criteria. No customer access or sharing.',
      } }],
  }));
  for (const tool of tools) {
    registerAppTool(server, tool.name, {
      title: tool.title, description: tool.description,
      inputSchema: tool.schema, outputSchema: snapshotSchema,
      annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false, idempotentHint: true },
      _meta: { ui: { resourceUri: WIDGET_URI, visibility: ['model', 'app'] },
        'openai/toolInvocation/invoking': 'Reading fictional catalog data',
        'openai/toolInvocation/invoked': 'Demo ready. No live data accessed.' },
    }, async args => toolResult(snapshot(tool.view, args.case_id)));
  }
  return server;
}
