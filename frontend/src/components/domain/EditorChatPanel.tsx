import React, { useState } from "react";
import { BlogChatMessage, BlogChatResponse } from "../../types";
import { Send, Bot, User, Sparkles, AlertCircle, History } from "lucide-react";
import { Button } from "../ui/Button";

export interface EditorChatPanelProps {
  messages: BlogChatMessage[];
  onSendMessage: (message: string) => Promise<BlogChatResponse | void>;
  isLoading?: boolean;
  latestRevisionNumber?: number;
  onViewRevisions?: () => void;
  readOnly?: boolean;
}

export const EditorChatPanel: React.FC<EditorChatPanelProps> = ({
  messages,
  onSendMessage,
  isLoading = false,
  latestRevisionNumber,
  onViewRevisions,
  readOnly = false,
}) => {
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading || readOnly) return;

    const messageText = input.trim();
    setInput("");
    setError(null);

    try {
      await onSendMessage(messageText);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to process conversational revision.");
      }
    }
  };

  return (
    <div className="bg-surface border border-border rounded-lg flex flex-col h-[700px] shadow-subtle">
      {/* Header */}
      <div className="p-4 border-b border-border flex items-center justify-between bg-background rounded-t-lg">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded bg-black text-white flex items-center justify-center">
            <Sparkles className="w-3.5 h-3.5 text-primary" />
          </div>
          <div>
            <h3 className="text-xs font-semibold text-near-black">
              AI Editorial Assistant
            </h3>
            <p className="text-[10px] text-muted">
              Conversational Revisions (Phase 8)
            </p>
          </div>
        </div>
        {onViewRevisions && (
          <Button
            size="sm"
            variant="outline"
            onClick={onViewRevisions}
            leftIcon={<History className="w-3.5 h-3.5" />}
          >
            v{latestRevisionNumber ?? 0} History
          </Button>
        )}
      </div>

      {/* Message history */}
      <div className="flex-1 p-4 overflow-y-auto space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-muted">
            <Bot className="w-8 h-8 text-primary mb-2 opacity-60" />
            <p className="text-xs font-medium text-near-black">
              Ask AI to refine this blog
            </p>
            <p className="text-[11px] max-w-xs mt-1 leading-relaxed">
              &quot;Make the introduction punchier&quot;, &quot;Add data points to section 2&quot;, or &quot;Shorten conclusion&quot;.
            </p>
          </div>
        ) : (
          messages.map((msg) => {
            const isUser = msg.sender_type === "USER" || msg.sender_type === "editor";
            return (
              <div
                key={msg.id}
                className={`flex gap-2.5 ${
                  isUser ? "justify-end" : "justify-start"
                }`}
              >
                {!isUser && (
                  <div className="w-6 h-6 rounded-full bg-near-black text-primary flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Bot className="w-3.5 h-3.5" />
                  </div>
                )}
                <div
                  className={`max-w-[85%] rounded-lg p-3 text-xs leading-relaxed ${
                    isUser
                      ? "bg-near-black text-white"
                      : "bg-background border border-border text-near-black"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                  {Boolean(msg.message_metadata?.created_revision_id) && (
                    <div className="mt-2 pt-2 border-t border-border/40 text-[10px] flex items-center gap-1.5 text-primary font-mono font-medium">
                      <Sparkles className="w-3 h-3" />
                      Created Revision #{String(msg.message_metadata?.created_revision_id)}
                    </div>
                  )}
                  <span
                    className={`block text-[9px] mt-1 font-mono ${
                      isUser ? "text-gray-400 text-right" : "text-muted"
                    }`}
                  >
                    {new Date(msg.created_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
                {isUser && (
                  <div className="w-6 h-6 rounded-full bg-primary text-white flex items-center justify-center flex-shrink-0 mt-0.5">
                    <User className="w-3.5 h-3.5" />
                  </div>
                )}
              </div>
            );
          })
        )}

        {isLoading && (
          <div className="flex gap-2.5 justify-start">
            <div className="w-6 h-6 rounded-full bg-near-black text-primary flex items-center justify-center flex-shrink-0 animate-pulse">
              <Bot className="w-3.5 h-3.5" />
            </div>
            <div className="bg-background border border-border rounded-lg p-3 text-xs text-muted flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-primary animate-ping" />
              <span>Analyzing instruction &amp; validating revision...</span>
            </div>
          </div>
        )}
      </div>

      {/* Error alert */}
      {error && (
        <div className="px-4 py-2 bg-primary-light border-t border-primary-border flex items-center gap-2 text-xs text-primary-dark">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span className="truncate">{error}</span>
        </div>
      )}

      {/* Input Form */}
      <form
        onSubmit={handleSend}
        className="p-3 border-t border-border bg-background rounded-b-lg flex items-center gap-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            readOnly
              ? "Read-only mode: only Editors can request revisions"
              : "Instruction: e.g. Make introduction concise..."
          }
          disabled={isLoading || readOnly}
          className="flex-1 bg-surface border border-border rounded px-3 py-2 text-xs text-near-black placeholder:text-muted/60 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary disabled:opacity-50"
        />
        <Button
          type="submit"
          size="sm"
          variant="primary"
          disabled={!input.trim() || isLoading || readOnly}
          isLoading={isLoading}
          aria-label="Send revision instruction"
        >
          <Send className="w-3.5 h-3.5" />
        </Button>
      </form>
    </div>
  );
};
