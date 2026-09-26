import React from "react";
import { TopicCandidate } from "../../types";
import { StatusBadge } from "../ui/StatusBadge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Check, X, Sparkles, Key, Target, Compass } from "lucide-react";
import { useAuth } from "../../contexts/AuthContext";

export interface TopicCardProps {
  topic: TopicCandidate;
  onSelect?: (topicId: number) => void;
  onReject?: (topicId: number) => void;
  onGenerateBlog?: (topicId: number) => void;
  isActionLoading?: boolean;
}

export const TopicCard: React.FC<TopicCardProps> = ({
  topic,
  onSelect,
  onReject,
  onGenerateBlog,
  isActionLoading = false,
}) => {
  const { role } = useAuth();
  const isEditor = role === "editor";

  return (
    <Card className="hover:border-gray-400 transition-colors duration-150 flex flex-col justify-between">
      <div className="p-5">
        <div className="flex items-start justify-between gap-3 mb-3">
          <StatusBadge status={topic.status} size="sm" />
          <div className="flex items-center gap-1.5 text-[11px] text-muted font-mono">
            <span>Score:</span>
            <span className="font-semibold text-near-black">
              {(topic.final_score * 100).toFixed(0)}%
            </span>
          </div>
        </div>

        <h3 className="text-base font-semibold text-near-black leading-snug mb-2">
          {topic.title}
        </h3>

        <div className="space-y-2 mb-4">
          <div className="flex items-start gap-2 text-xs text-muted">
            <Compass className="w-3.5 h-3.5 mt-0.5 text-primary flex-shrink-0" />
            <span className="leading-relaxed">
              <strong className="text-near-black font-medium">Angle:</strong>{" "}
              {topic.angle}
            </span>
          </div>
          <div className="flex items-start gap-2 text-xs text-muted">
            <Target className="w-3.5 h-3.5 mt-0.5 text-primary flex-shrink-0" />
            <span className="leading-relaxed">
              <strong className="text-near-black font-medium">Rationale:</strong>{" "}
              {topic.rationale}
            </span>
          </div>
        </div>

        <div className="pt-3 border-t border-border flex flex-wrap items-center gap-2 text-xs">
          <div className="inline-flex items-center gap-1 bg-background px-2 py-0.5 rounded border border-border text-muted">
            <Key className="w-3 h-3 text-primary" />
            <span className="font-mono text-[11px] text-near-black font-medium">
              {topic.primary_keyword}
            </span>
          </div>
          {topic.target_audience && (
            <span className="text-[11px] text-muted">
              Audience: {topic.target_audience}
            </span>
          )}
        </div>
      </div>

      {/* Action Footer */}
      <div className="p-3 bg-background border-t border-border rounded-b-lg flex items-center justify-between gap-2">
        <div className="text-[11px] text-muted">
          Relevance: {(topic.relevance_score * 100).toFixed(0)}% | Freshness:{" "}
          {(topic.freshness_score * 100).toFixed(0)}%
        </div>

        <div className="flex items-center gap-2">
          {isEditor && topic.status === "suggested" && (
            <>
              {onReject && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => onReject(topic.id)}
                  disabled={isActionLoading}
                  leftIcon={<X className="w-3.5 h-3.5" />}
                  title="Reject topic"
                >
                  Reject
                </Button>
              )}
              {onSelect && (
                <Button
                  size="sm"
                  variant="primary"
                  onClick={() => onSelect(topic.id)}
                  disabled={isActionLoading}
                  leftIcon={<Check className="w-3.5 h-3.5" />}
                >
                  Select
                </Button>
              )}
            </>
          )}

          {isEditor && topic.status === "selected" && onGenerateBlog && (
            <Button
              size="sm"
              variant="dark"
              onClick={() => onGenerateBlog(topic.id)}
              disabled={isActionLoading}
              leftIcon={<Sparkles className="w-3.5 h-3.5 text-primary" />}
            >
              Generate Blog
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
};
