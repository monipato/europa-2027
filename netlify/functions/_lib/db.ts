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
