'use client';

import React from 'react';
import { useParams } from 'next/navigation';
import { ChatView } from '@/features/chat';

export default function ChatDetailPage() {
  const params = useParams<{ chatId: string }>();
  const chatId = params.chatId;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <ChatView chatId={chatId} />
    </div>
  );
}
