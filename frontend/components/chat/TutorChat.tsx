"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { streamTutorChat } from "@/utilities/streaming";
import { supabase } from "@/utilities/supabase";
import type { ChatDone, Citation } from "@/types/tutor";
import styles from "./TutorChat.module.css";

type Message = {
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
};

const EMPTY_STATE =
  "Ask me anything about your certification material. I’ll answer with citations to the study content.";

export default function TutorChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState("");
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [session, setSession] = useState<boolean | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let active = true;
    supabase.auth.getSession().then(({ data }) => {
      if (active) setSession(Boolean(data.session));
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = input.trim();
    if (!message || streaming) return;

    setError("");
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: message }]);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    // Reserve an assistant slot we append to as deltas arrive.
    setMessages((prev) => [...prev, { role: "assistant", text: "" }]);

    try {
      await streamTutorChat(
        { message, conversation_id: conversationId },
        {
          onMeta: (meta) => {
            if (meta.conversation_id) setConversationId(meta.conversation_id);
          },
          onDelta: (text) => {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (last?.role === "assistant") {
                next[next.length - 1] = { ...last, text: last.text + text };
              }
              return next;
            });
          },
          onDone: (done: ChatDone) => {
            setConversationId(done.conversation_id);
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (last?.role === "assistant") {
                next[next.length - 1] = {
                  role: "assistant",
                  text: done.answer,
                  citations: done.citations,
                };
              }
              return next;
            });
          },
          onError: (detail) => {
            setError(detail);
          },
        },
        controller.signal,
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "The tutor didn’t respond. Try again.",
      );
      // Remove the empty assistant slot we reserved.
      setMessages((prev) =>
        prev[prev.length - 1]?.role === "assistant" && prev[prev.length - 1].text === ""
          ? prev.slice(0, -1)
          : prev,
      );
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }

  function stopStreaming() {
    abortRef.current?.abort();
  }

  if (session === null) {
    return <p className={styles.placeholder}>Loading…</p>;
  }

  if (session === false) {
    return (
      <div className={styles.signIn}>
        <h2>Log in to use the tutor</h2>
        <p>Your study questions and conversation history are saved to your account.</p>
        <a className={styles.button} href="/login">
          Log in
        </a>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      <header className={styles.header}>
        <h1>AI Tutor</h1>
        <p>Ask a question, get an answer backed by your study material.</p>
      </header>

      <div className={styles.messages}>
        {messages.length === 0 && (
          <p className={styles.empty}>{EMPTY_STATE}</p>
        )}

        {messages.map((message, index) => (
          <article
            key={index}
            className={
              message.role === "user" ? styles.userMessage : styles.assistantMessage
            }
          >
            <div className={styles.bubble}>
              {message.role === "assistant" && !message.text && streaming ? (
                <span className={styles.typing}>Thinking…</span>
              ) : (
                <p className={styles.text}>{message.text}</p>
              )}
              {message.citations && message.citations.length > 0 && (
                <footer className={styles.citations}>
                  <h3>Sources</h3>
                  <ol>
                    {message.citations.map((citation) => (
                      <li key={citation.source_id}>
                        <span className={styles.sourceId}>{citation.source_id}</span>{" "}
                        {citation.source_url ? (
                          <a href={citation.source_url} target="_blank" rel="noreferrer">
                            {citation.document_title}
                          </a>
                        ) : (
                          citation.document_title
                        )}
                        {citation.domain && (
                          <span className={styles.domain}> · {citation.domain}</span>
                        )}
                      </li>
                    ))}
                  </ol>
                </footer>
              )}
            </div>
          </article>
        ))}
        <div ref={bottomRef} />
      </div>

      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}

      <form className={styles.composer} onSubmit={handleSubmit}>
        <input
          className={styles.input}
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask about your certification…"
          disabled={streaming}
          aria-label="Ask the tutor a question"
        />
        {streaming ? (
          <button
            className={styles.send}
            type="button"
            onClick={stopStreaming}
            aria-label="Stop generating"
          >
            Stop
          </button>
        ) : (
          <button
            className={styles.send}
            type="submit"
            disabled={!input.trim()}
            aria-label="Send"
          >
            Send
          </button>
        )}
      </form>
    </div>
  );
}
