Create a private-conversation digest for the direct conversation with
`$person`, covering the last $days days.

Scope and retrieval
- Process only the specified one-to-one conversation with a person.
- Do not process channels, groups, bots, or other conversations.
- Do not treat forwarded channel posts as channel content. Consider them only
  when they materially affect this direct conversation.
- Use only locally cached data. Do not contact Telegram directly and do not
  trigger synchronization, updates, refreshes, or other network operations.
- Read the selected direct conversation once for the requested period.
- If the conversation cannot be read from the cache, state that it is
  unavailable and stop.
- If there are no cached messages in the requested period, state this
  explicitly and stop.

Analysis principles
- Base conclusions only on messages available within the requested period.
- Separate explicit facts from cautious interpretation.
- Prioritize concrete events, decisions, commitments, blockers, deadlines,
  unresolved questions, and changes of direction over casual discussion.
- Do not invent context, intentions, requirements, decisions, dates, owners,
  deadlines, or outcomes.
- When evidence is incomplete, write "unclear from the available messages".
- You may make a cautious inference only when it is grounded in specific
  messages. Label it as an inference, not as a fact.
- Do not turn a weak signal into a confident conclusion.
- If participants disagree, describe the disagreement neutrally and attribute
  each position.
- Preserve status precisely: distinguish proposals, tentative plans, agreed
  decisions, commitments, and completed actions.

Perspective
Act as a senior software and systems architect reviewing a working
conversation. Where supported by the messages, assess:
- goals and business or technical context;
- requirements, constraints, assumptions, and dependencies;
- architecture, integration, interfaces, data flows, and delivery implications;
- decisions and their stated rationale;
- security, reliability, observability, deployment, and operational concerns;
- ownership, commitments, deadlines, blockers, and next actions;
- questions that must be answered before a sound technical decision can be made.

Do not force every category into the answer. Omit sections unsupported by the
conversation. Do not add generic architecture advice merely to fill a section.

Output format
Use this Markdown structure exactly:

# Conversation digest

## Key developments
Use bullets. State meaningful events, changes, discoveries, proposals, or
decisions.

## Decisions and commitments
Use bullets. Label every item as exactly one of: Decision, Tentative decision,
Commitment, Proposal, or No decision. Include a responsible person or deadline
only when explicitly stated.

## Architecture
Use bullets only for concerns supported by the messages. Cover relevant
requirements, interfaces, dependencies, reliability, security, observability,
deployment, ownership, and operational risks. Clearly distinguish explicit
discussion points from cautious architect-level inferences.

## Open questions and risks
Use bullets. For each item, explain why it matters and what information is
missing. Do not create generic risks to fill the section.

## Recommended next steps
Provide 2 to 5 concrete and proportionate actions derived from an identified
decision, blocker, risk, or unanswered question. Do not present speculative
recommendations as agreed work.

## Clarification questions
Ask only questions whose answers would materially change a technical decision,
delivery plan, integration design, or risk assessment. Do not ask questions
already answered in the messages. If none are needed, write:
"No material clarification questions identified."

## Direct answer options
Provide 2 to 4 short, ready-to-send reply drafts that the user can copy and
paste directly into the conversation with the selected person.
- Base every draft strictly on the conversation, its open questions, decisions,
  commitments, and next steps.
- Write each option in the first person, as if sent by the user.
- Do not reveal that this digest, cached data, tools, or an AI system was used.
- Make each option distinct in purpose, when supported by the conversation:
  clarification request, confirmation of a decision, follow-up on an action,
  concise status update, or proposal for the next step.
- Keep each draft concise and natural: normally 1 to 4 sentences.
- Use the recipient's preferred name only if it is clearly known from the
  conversation; otherwise do not add a greeting.

## Evidence
For every major conclusion, decision, commitment, risk, recommendation, or
clarification question, include relevant message timestamps or message IDs in
parentheses. Use references for traceability; do not quote long message
passages.

Selected direct conversation: $person.
Requested period: last $days days.