import React from "react";

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-[#050505] text-white">
          <div className="text-center p-8">
            <h1 className="text-3xl font-bold mb-4 text-[#FF3B30]">Erro na página</h1>
            <p className="text-[#A1A1AA] mb-6">{this.state.error?.message || "Algo deu errado"}</p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              className="bg-[#007AFF] px-6 py-2 rounded hover:bg-[#0056b3]"
            >
              Recarregar
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
