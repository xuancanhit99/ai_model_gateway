import { Component, ErrorInfo, ReactNode } from 'react'; // Removed unused React import
import { Alert, AlertTitle, Box, Typography, Button } from '@mui/material';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  // This lifecycle method is invoked after an error has been thrown by a descendant component.
  public static getDerivedStateFromError(_: Error): State {
    // Update state so the next render will show the fallback UI.
    return { hasError: true, error: _, errorInfo: null }; // Store error but clear errorInfo initially
  }

  // This lifecycle method is invoked after an error has been thrown by a descendant component.
  // It receives the error and information about which component threw the error.
  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // You can also log the error to an error reporting service here
    console.error("Uncaught error:", error, errorInfo);
    // Update state with detailed error info
    this.setState({ error, errorInfo });
  }

  private handleReload = () => {
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      // You can render any custom fallback UI
      return (
        <Box sx={{ p: 4, display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
          <Alert severity="error" sx={{ maxWidth: 600, width: '100%' }}>
            <AlertTitle>Oops! Something went wrong.</AlertTitle>
            <Typography variant="body2" gutterBottom>
              An unexpected error occurred in the application. Please try reloading the page.
            </Typography>
            {/* Optionally display error details for debugging (in development) */}
            {import.meta.env.DEV && this.state.error && (
              <details style={{ whiteSpace: 'pre-wrap', marginTop: '10px' }}>
                <summary>Error Details</summary>
                {this.state.error.toString()}
                <br />
                {this.state.errorInfo?.componentStack}
              </details>
            )}
             <Button
                variant="outlined"
                color="error"
                onClick={this.handleReload}
                sx={{ mt: 2 }}
            >
                Reload Page
            </Button>
          </Alert>
        </Box>
      );
    }

    // Normally, just render children
    return this.props.children;
  }
}

export default ErrorBoundary;
