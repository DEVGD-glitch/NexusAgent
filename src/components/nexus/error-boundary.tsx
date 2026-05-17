// ═══════════════════════════════════════════════════════════════
// NEXUS — Error Boundary
// Catches React crashes and shows a recovery UI
// ═══════════════════════════════════════════════════════════════

"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { AlertCircle, RefreshCw } from "lucide-react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.props.onError?.(error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex flex-col items-center justify-center gap-3 p-6 rounded-xl border border-red-500/20 bg-red-500/5">
          <AlertCircle size={24} className="text-red-400" />
          <div className="text-center">
            <p className="text-sm font-medium text-foreground">
              Something went wrong
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {this.state.error?.message || "An unexpected error occurred"}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={this.handleReset}
            className="gap-1.5"
          >
            <RefreshCw size={12} />
            Try again
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}
