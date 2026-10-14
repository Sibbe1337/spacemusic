import { z } from 'zod';

export const CASE_IDS = ['demo-harbor', 'demo-juniper', 'demo-northline'];
export const caseIdSchema = z.enum(CASE_IDS);
export const noInputSchema = z.object({}).strict();
export const caseInputSchema = z.object({ case_id: caseIdSchema }).strict();
const text = z.string().min(1).max(1200);
const checkSchema = z.object({
  id: text, label: text, status: z.enum(['provided', 'missing', 'clarify']),
  finding: text, nextStep: text, sourceId: text,
}).strict();
const summarySchema = z.object({
  id: caseIdSchema, name: text, rights: text, description: text,
  provided: z.number().int().min(0).max(6), total: z.literal(6),
  nextStep: text,
}).strict();
const detailSchema = summarySchema.extend({
  offeredShare: text, financialContext: text,
  checks: z.array(checkSchema).length(6),
  sources: z.array(z.object({ id: text, label: text, note: text }).strict()).max(8),
}).strict();
const matchSchema = z.object({
  id: text, name: text, status: z.enum(['potential', 'blocked', 'outside_scope']),
  criteria: text, reasons: z.array(text).min(1).max(8), sourceId: text,
}).strict();

export const snapshotSchema = z.object({
  schemaVersion: z.literal(1),
  dataMode: z.literal('synthetic'),
  asOf: z.literal('2026-10-03'),
  view: z.enum(['overview', 'review', 'buyers']),
  notice: text,
  sharingEnabled: z.literal(false),
  cases: z.array(summarySchema).length(3),
  selected: detailSchema.nullable(),
  matches: z.array(matchSchema).max(3),
}).strict().superRefine((value, context) => {
  if ((value.view === 'overview') !== (value.selected === null)) {
    context.addIssue({ code: 'custom', message: 'View and selected catalog must agree' });
  }
  if (value.view !== 'buyers' && value.matches.length) {
    context.addIssue({ code: 'custom', message: 'Buyer profiles belong only in the buyer view' });
  }
});
