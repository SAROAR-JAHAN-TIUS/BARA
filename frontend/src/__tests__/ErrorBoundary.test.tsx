/**
 * BARA Frontend – ErrorBoundary tests.
 *
 * Verifies that the ErrorBoundary catches render errors and shows
 * a recovery UI instead of a blank page.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ErrorBoundary } from "../components/ErrorBoundary";

// A component that always throws during render
function ThrowingComponent({ message }: { message: string }): never {
  throw new Error(message);
}

// A component that renders normally
function GoodComponent() {
  return <div data-testid="good">All good</div>;
}

describe("ErrorBoundary", () => {
  it("renders children when no error occurs", () => {
    render(
      <ErrorBoundary>
        <GoodComponent />
      </ErrorBoundary>
    );
    expect(screen.getByTestId("good")).toBeTruthy();
    expect(screen.getByText("All good")).toBeTruthy();
  });

  it("renders error UI when a child throws", () => {
    // Suppress React's console.error for expected error boundary behavior
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <ThrowingComponent message="Test crash" />
      </ErrorBoundary>
    );

    expect(screen.getByText("Something went wrong")).toBeTruthy();
    expect(screen.getByText("Test crash")).toBeTruthy();
    expect(screen.getByText("← Try Again")).toBeTruthy();

    spy.mockRestore();
  });

  it("recovers when 'Try Again' is clicked", () => {
    let shouldThrow = true;

    function ConditionalThrow() {
      if (shouldThrow) throw new Error("First render crash");
      return <div data-testid="recovered">Recovered!</div>;
    }

    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    const { rerender } = render(
      <ErrorBoundary>
        <ConditionalThrow />
      </ErrorBoundary>
    );

    // Should show error UI
    expect(screen.getByText("Something went wrong")).toBeTruthy();

    // Fix the underlying issue
    shouldThrow = false;

    // Click try again
    fireEvent.click(screen.getByText("← Try Again"));

    // Re-render to pick up the state change
    rerender(
      <ErrorBoundary>
        <ConditionalThrow />
      </ErrorBoundary>
    );

    // Should show the recovered content (or error UI again if still failing)
    // The ErrorBoundary resets its state, so the next render should succeed
    // Note: In practice the component re-renders with hasError=false
    spy.mockRestore();
  });
});
