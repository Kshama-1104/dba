import React from "react";
import { Link } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { Sparkles, FileText, ArrowRight, CheckCircle2, Bot } from "lucide-react";

export const LandingPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-background font-sans selection:bg-primary-light">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-near-black flex items-center justify-center">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold tracking-tight text-near-black">
              DailyBlog AI
            </span>
          </div>
          <nav className="hidden md:flex items-center gap-6">
            <a href="#features" className="text-sm font-medium text-muted hover:text-near-black transition-colors">Features</a>
            <a href="#workflow" className="text-sm font-medium text-muted hover:text-near-black transition-colors">How it Works</a>
            <div className="flex items-center gap-3 ml-4">
              <Link to="/login">
                <Button variant="outline" size="sm">Log in</Button>
              </Link>
              <Link to="/register">
                <Button variant="primary" size="sm">Get Started</Button>
              </Link>
            </div>
          </nav>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative pt-24 pb-32 overflow-hidden">
        <div className="container mx-auto px-4 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary-light/50 border border-primary-light text-primary-dark text-sm font-medium mb-8">
            <Sparkles className="w-4 h-4" />
            <span>The future of B2B content marketing</span>
          </div>
          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight text-near-black max-w-4xl mx-auto mb-8 leading-tight">
            Automate your editorial pipeline with <span className="text-primary">Enterprise AI</span>
          </h1>
          <p className="text-lg md:text-xl text-muted max-w-2xl mx-auto mb-10 leading-relaxed">
            DailyBlog AI generates, optimizes, reviews, and publishes SEO-rich articles tailored to your brand voice. Full Separation of Duties built in.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link to="/register">
              <Button size="lg" variant="primary" rightIcon={<ArrowRight className="w-5 h-5" />}>
                Start your free workspace
              </Button>
            </Link>
            <Link to="/register/reviewer">
              <Button size="lg" variant="outline">
                Join as Reviewer
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section id="features" className="py-24 bg-surface border-y border-border">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold tracking-tight text-near-black mb-4">Enterprise-Grade Workflows</h2>
            <p className="text-muted max-w-xl mx-auto">Designed for content teams that require strict governance and high-quality outputs.</p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            <FeatureCard 
              title="Brand Memory & RAG" 
              description="Ingest PDFs, guidelines, and company knowledge. Our 384-dimensional pgvector RAG pipeline ensures the AI never hallucinates your core messaging."
            />
            <FeatureCard 
              title="Separation of Duties" 
              description="Strict RBAC separating Editors from Reviewers. Drafts must pass a deterministic SEO validation gate and human approval before scheduling."
            />
            <FeatureCard 
              title="Automated Publishing" 
              description="Schedule approved posts to your WordPress site with timezone-aware workers. We handle SSRF protection and HTML sanitization automatically."
            />
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 bg-background">
        <div className="container mx-auto px-4 text-center">
          <p className="text-sm text-muted">© 2026 DailyBlog AI. Assessment Deliverable.</p>
        </div>
      </footer>
    </div>
  );
};

const FeatureCard = ({ title, description }: { title: string, description: string }) => (
  <div className="p-6 bg-background rounded-xl border border-border shadow-subtle text-left">
    <div className="w-10 h-10 rounded-lg bg-primary-light flex items-center justify-center mb-4">
      <CheckCircle2 className="w-5 h-5 text-primary-dark" />
    </div>
    <h3 className="text-lg font-bold text-near-black mb-2">{title}</h3>
    <p className="text-muted leading-relaxed text-sm">{description}</p>
  </div>
);
