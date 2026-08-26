import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({ breaks: true })

/** Assistant/user text is plain but may contain markdown (lists, bold,
 * `code`, links) — render it properly instead of dumping raw asterisks
 * and backticks at the customer. Sanitize since the LLM's own output
 * (and, for user bubbles, the customer's own input) both land in v-html. */
export function renderMarkdown(text: string): string {
  const html = marked.parse(text, { async: false })
  return DOMPurify.sanitize(html)
}
