import { openDB, DBSchema, IDBPDatabase } from 'idb';
import type { Conversation, Message } from '@/types/nexus';

interface NexusDB extends DBSchema {
  conversations: {
    key: string;
    value: Conversation;
    indexes: { 'by-updated': number };
  };
  messages: {
    key: string;
    value: Message & { conversationId: string };
    indexes: { 'by-conversation': string };
  };
}

const DB_NAME = 'nexus-db';
const DB_VERSION = 1;

let dbPromise: Promise<IDBPDatabase<NexusDB>> | null = null;

function getDB(): Promise<IDBPDatabase<NexusDB>> {
  if (!dbPromise) {
    dbPromise = openDB<NexusDB>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains('conversations')) {
          const convStore = db.createObjectStore('conversations', { keyPath: 'id' });
          convStore.createIndex('by-updated', 'updatedAt');
        }
        if (!db.objectStoreNames.contains('messages')) {
          const msgStore = db.createObjectStore('messages', { keyPath: 'id' });
          msgStore.createIndex('by-conversation', 'conversationId');
        }
      },
    });
  }
  return dbPromise;
}

// Conversations
export async function saveConversation(conv: Conversation): Promise<void> {
  const db = await getDB();
  await db.put('conversations', { ...conv, updatedAt: Date.now() });
}

export async function getConversation(id: string): Promise<Conversation | undefined> {
  const db = await getDB();
  return db.get('conversations', id);
}

export async function getAllConversations(): Promise<Conversation[]> {
  const db = await getDB();
  return db.getAllFromIndex('conversations', 'by-updated');
}

export async function deleteConversation(id: string): Promise<void> {
  const db = await getDB();
  await db.delete('conversations', id);
  // Also delete associated messages
  const msgs = await db.getAllFromIndex('messages', 'by-conversation', id);
  for (const msg of msgs) {
    await db.delete('messages', msg.id);
  }
}

// Messages
export async function saveMessage(msg: Message & { conversationId: string }): Promise<void> {
  const db = await getDB();
  await db.put('messages', msg);
}

export async function getMessages(conversationId: string): Promise<(Message & { conversationId: string })[]> {
  const db = await getDB();
  return db.getAllFromIndex('messages', 'by-conversation', conversationId);
}

export async function clearAll(): Promise<void> {
  const db = await getDB();
  await db.clear('conversations');
  await db.clear('messages');
}
