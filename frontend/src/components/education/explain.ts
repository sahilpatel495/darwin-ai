// Every "what's this?" explanation in the product, in one file (§10).
//
// Why one file: the same seven ideas are explained in the sidebar, beside an answer and inside
// the clarify question. Written once, they stay consistent; written seven times they drift, and
// the analyst meets two different definitions of the same word in the same screen.
//
// The shape is exactly the props of the WhatsThis primitive, so a caller writes
// `<WhatsThis {...EXPLAIN.links} />`.
//
// Rules for the copy (§8): what it means, then why the analyst should care. Two sentences.
// Sentence case, no jargon — never "schema", "join", "payload", "pipeline", "LLM", "session".
// No runtime imports: education.test.mjs loads this file directly with `node --test`.

export type ExplainKey = 'confidence' | 'crossCheck' | 'definition' | 'dataHealth' | 'links' | 'combined' | 'clarify'

export interface Explanation {
  /** The heading inside the panel. A question or a short noun phrase, sentence case. */
  title: string
  /** Two sentences: what it means, then why it matters to the person reading it. */
  body: string
}

export const EXPLAIN: Record<ExplainKey, Explanation> = {
  confidence: {
    title: 'What the rating means',
    body: 'It says how well your question matched your data and how many of the checks passed, on a scale of high, medium and low. A high rating is one you can quote in a meeting; anything lower is worth opening the working before you do.',
  },
  crossCheck: {
    title: 'Why a second model matters',
    body: 'A different AI model was given the same question and wrote its own query, without seeing the first one. When both queries return the same number, a mistake in either one would have shown up as a disagreement.',
  },
  definition: {
    title: 'Your agreed definition',
    body: 'A measure like attrition can be worked out three or four ways, so DarwinLens uses the definition written in your glossary instead of picking one. Change it there and every answer that uses that measure follows your company, not a default.',
  },
  dataHealth: {
    title: 'What Data Health shows',
    body: 'Every change made to a file while it was read, counted line by line: title rows skipped, total rows dropped, duplicates removed, amounts that could not be read. Nothing is cleaned quietly, so you can see whether a number is missing rows before you rely on it.',
  },
  links: {
    title: 'Why links matter',
    body: 'A link says which rows in two files describe the same person, so pay from one file can be counted next to headcount from another. A wrong link counts the same pay twice, which is why you can remove any link you do not recognise.',
  },
  combined: {
    title: 'What a combined view is',
    body: 'When several files hold the same kind of rows, one per month for example, DarwinLens stacks them into a single view so one question covers them all. Your files are not changed, and removing the view puts the question back to one file at a time.',
  },
  clarify: {
    title: 'Why am I asking?',
    body: 'Your wording matches more than one column in your files, so there is no single right reading of the question. Guessing would give you a confident wrong number, which is worse than one more click.',
  },
}
