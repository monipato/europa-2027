// Minimal Postgres access for the WhatsApp bot (conversations + messages).
// Uses Neon's serverless driver over plain HTTPS, so it works from any host
// (Netlify Functions included) — just needs a DATABASE_URL/POSTGRES_URL env var
// pointing at a Neon (or any Postgres) connection string.
import { neon } from '@neondatabase/serverless'

const sql = neon(process.env.DATABASE_URL || process.env.POSTGRES_URL || '')

export type Conversation = {
  id: number
  phoneNumber: string
  contactPhone: string | null
  aiPaused: boolean
}

export type StoredMessage = {
  sender: 'customer' | 'ai' | 'admin'
  body: string
}

let schemaReady: Promise<void> | null = null

/** Creates the tables on first use of a warm function instance. Idempotent. */
export function ensureSchema(): Promise<void> {
  if (!schemaReady) {
    schemaReady = (async () => {
      await sql`
        CREATE TABLE IF NOT EXISTS conversations (
          id SERIAL PRIMARY KEY,
          phone_number TEXT UNIQUE NOT NULL,
          contact_phone TEXT,
          ai_paused BOOLEAN NOT NULL DEFAULT FALSE,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
      `
      await sql`
        CREATE TABLE IF NOT EXISTS messages (
          id SERIAL PRIMARY KEY,
          conversation_id INTEGER NOT NULL REFERENCES conversations(id),
          whatsapp_message_id TEXT UNIQUE,
          direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
          sender TEXT NOT NULL CHECK (sender IN ('customer', 'ai', 'admin')),
          body TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
      `
    })()
  }
  return schemaReady
}

type ConversationRow = { id: number; phone_number: string; contact_phone: string | null; ai_paused: boolean }

/** Same conversations table, keyed by a "web:<sessionId>" pseudo phone
 * number instead of a real one — lets the in-app chat widget reuse the exact
 * same schema/history/dedup machinery as the WhatsApp bot without a
 * migration, the same way a WhatsApp `From` value is namespaced as
 * "whatsapp:+57...". */
export function getOrCreateConversationBySession(sessionId: string): Promise<Conversation> {
  return getOrCreateConversation(`web:${sessionId}`)
}

/** Read-only counterpart to getOrCreateConversationBySession — used to load
 * a session's saved history without creating an (empty) conversation row
 * for every visitor who merely opens the chat widget without sending a
 * message. Conversations are never deleted, only ever read or added to. */
export async function findConversationBySession(sessionId: string): Promise<Conversation | null> {
  const rows = (await sql`
    SELECT id, phone_number, contact_phone, ai_paused FROM conversations WHERE phone_number = ${`web:${sessionId}`}
  `) as ConversationRow[]
  if (!rows.length) return null
  const row = rows[0]
  return { id: row.id, phoneNumber: row.phone_number, contactPhone: row.contact_phone, aiPaused: row.ai_paused }
}

export async function getOrCreateConversation(phoneNumber: string): Promise<Conversation> {
  const rows = (await sql`
    INSERT INTO conversations (phone_number)
    VALUES (${phoneNumber})
    ON CONFLICT (phone_number) DO UPDATE SET updated_at = now()
    RETURNING id, phone_number, contact_phone, ai_paused
  `) as ConversationRow[]
  const row = rows[0]
  return { id: row.id, phoneNumber: row.phone_number, contactPhone: row.contact_phone, aiPaused: row.ai_paused }
}

/**
 * Records an inbound message. Returns false (and inserts nothing) if this
 * WhatsApp message id was already processed — Twilio retries webhooks that
 * don't ack fast enough, so this is the dedup guard from spec step 4.4.
 */
export async function insertInboundMessage(
  conversationId: number,
  whatsappMessageId: string,
  body: string,
): Promise<boolean> {
  const rows = await sql`
    INSERT INTO messages (conversation_id, whatsapp_message_id, direction, sender, body)
    VALUES (${conversationId}, ${whatsappMessageId}, 'inbound', 'customer', ${body})
    ON CONFLICT (whatsapp_message_id) DO NOTHING
    RETURNING id
  `
  return rows.length > 0
}

export async function insertOutboundMessage(
  conversationId: number,
  sender: 'ai' | 'admin',
  body: string,
): Promise<void> {
  await sql`
    INSERT INTO messages (conversation_id, direction, sender, body)
    VALUES (${conversationId}, 'outbound', ${sender}, ${body})
  `
}

export async function getRecentMessages(conversationId: number, limit = 20): Promise<StoredMessage[]> {
  const rows = (await sql`
    SELECT sender, body FROM messages
    WHERE conversation_id = ${conversationId}
    ORDER BY created_at DESC
    LIMIT ${limit}
  `) as StoredMessage[]
  return rows.reverse()
}

/** Default daily cap on customer messages per conversation before the bot
 * stops calling Gemini and asks them to wait — a WhatsApp number with no
 * login is otherwise an open door to unlimited (paid) API calls from a
 * single caller, deliberate or not. Overridable via env for a busier launch
 * day without a code change. */
const DAILY_MESSAGE_CAP = Number(process.env.CHAT_DAILY_MESSAGE_CAP) || 40

/** Whether this conversation has already sent DAILY_MESSAGE_CAP or more
 * inbound (customer) messages in the last rolling 24h — the abuse/cost
 * backstop for both chat.mts and twilio-whatsapp-webhook.mts. A generous
 * cap: it's there to stop a runaway loop or deliberate abuse, not to
 * interrupt a real, if unusually chatty, conversation. */
export async function hasReachedDailyMessageCap(conversationId: number): Promise<boolean> {
  const rows = (await sql`
    SELECT COUNT(*)::int AS count FROM messages
    WHERE conversation_id = ${conversationId}
      AND direction = 'inbound'
      AND created_at > now() - interval '24 hours'
  `) as { count: number }[]
  return (rows[0]?.count ?? 0) >= DAILY_MESSAGE_CAP
}
