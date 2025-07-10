// src/app/page.js
'use client';

import React, { useState, useEffect, useRef } from 'react';
import { 
  MessageSquare, 
  FileText, 
  Send, 
  Loader2, 
  ExternalLink, 
  Copy,
  Search,
  X
} from 'lucide-react';

const API_BASE = 'http://localhost:5000/api';

// Utility function for class names
function cn(...inputs) {
  return inputs.filter(Boolean).join(' ');
}

// UI Components
const Button = React.forwardRef(({ className, variant = "default", size = "default", children, ...props }, ref) => {
  const baseStyles = "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50";
  
  const variants = {
    default: "bg-blue-600 text-white hover:bg-blue-700",
    outline: "border border-gray-300 bg-background hover:bg-gray-50 hover:text-gray-900",
    ghost: "hover:bg-gray-100 hover:text-gray-900",
    secondary: "bg-gray-100 text-gray-900 hover:bg-gray-200",
  };
  
  const sizes = {
    default: "h-10 px-4 py-2",
    sm: "h-9 rounded-md px-3",
    lg: "h-11 rounded-md px-8",
    icon: "h-10 w-10",
  };

  return (
    <button
      className={cn(baseStyles, variants[variant], sizes[size], className)}
      ref={ref}
      {...props}
    >
      {children}
    </button>
  );
});

const Card = React.forwardRef(({ className, children, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("rounded-lg border bg-white text-gray-900 shadow-sm", className)}
    {...props}
  >
    {children}
  </div>
));

const CardHeader = React.forwardRef(({ className, children, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex flex-col space-y-1.5 p-6", className)}
    {...props}
  >
    {children}
  </div>
));

const CardTitle = React.forwardRef(({ className, children, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn("text-2xl font-semibold leading-none tracking-tight", className)}
    {...props}
  >
    {children}
  </h3>
));

const CardContent = React.forwardRef(({ className, children, ...props }, ref) => (
  <div ref={ref} className={cn("p-6 pt-0", className)} {...props}>
    {children}
  </div>
));

const Input = React.forwardRef(({ className, type, ...props }, ref) => {
  return (
    <input
      type={type}
      className={cn(
        "flex h-10 w-full rounded-md border border-gray-300 bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-gray-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      ref={ref}
      {...props}
    />
  );
});

const Textarea = React.forwardRef(({ className, ...props }, ref) => {
  return (
    <textarea
      className={cn(
        "flex min-h-[80px] w-full rounded-md border border-gray-300 bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-gray-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      ref={ref}
      {...props}
    />
  );
});

function Badge({ className, variant = "default", children, ...props }) {
  const variants = {
    default: "border-transparent bg-blue-600 text-white hover:bg-blue-700",
    secondary: "border-transparent bg-gray-100 text-gray-900 hover:bg-gray-200",
    outline: "text-gray-900",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
        variants[variant],
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

// Main Contract Proposal Generator Component
export default function ContractProposalGenerator() {
  const [step, setStep] = useState('select'); // 'select', 'processing', 'chat'
  const [suggestedContracts, setSuggestedContracts] = useState([]);
  const [customUrl, setCustomUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [contractContent, setContractContent] = useState('');
  const [highlightedText, setHighlightedText] = useState('');
  const [showHighlightModal, setShowHighlightModal] = useState(false);
  const [highlightInfo, setHighlightInfo] = useState(null);
  
  const messagesEndRef = useRef(null);
  const contractContentRef = useRef(null);

  useEffect(() => {
    fetchSuggestedContracts();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const fetchSuggestedContracts = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE}/contracts/suggested`);
      const data = await response.json();
      
      if (response.ok) {
        setSuggestedContracts(data.contracts);
      } else {
        console.error('Failed to fetch contracts:', data.error);
      }
    } catch (error) {
      console.error('Error fetching contracts:', error);
    } finally {
      setLoading(false);
    }
  };

  const processContract = async (url) => {
    try {
      setLoading(true);
      setStep('processing');
      
      const response = await fetch(`${API_BASE}/contracts/process`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url }),
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setSession(data);
        setContractContent(data.contract_content);
        setMessages([
          {
            type: 'ai',
            content: data.initial_outline,
            timestamp: new Date().toISOString()
          }
        ]);
        setStep('chat');
      } else {
        throw new Error(data.error);
      }
    } catch (error) {
      console.error('Error processing contract:', error);
      alert('Failed to process contract: ' + error.message);
      setStep('select');
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() || !session) return;

    const userMessage = {
      type: 'human',
      content: inputMessage,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: session.session_id,
          message: inputMessage,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        const aiMessage = {
          type: 'ai',
          content: data.answer,
          sources: data.sources,
          timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, aiMessage]);
      } else {
        throw new Error(data.error);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage = {
        type: 'ai',
        content: 'Sorry, I encountered an error processing your message.',
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
    }
  };

  const handleTextSelection = () => {
    const selection = window.getSelection();
    const selectedText = selection.toString().trim();
    
    if (selectedText && selectedText.length > 10) {
      setHighlightedText(selectedText);
      setShowHighlightModal(true);
    }
  };

  const handleHighlightQuestion = async () => {
    if (!highlightedText || !session) return;

    try {
      const response = await fetch(`${API_BASE}/highlight`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: session.session_id,
          highlighted_text: highlightedText,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        setHighlightInfo(data);
      } else {
        throw new Error(data.error);
      }
    } catch (error) {
      console.error('Error handling highlight:', error);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
  };

  const resetApp = () => {
    setStep('select');
    setSession(null);
    setMessages([]);
    setContractContent('');
    setCustomUrl('');
    setHighlightedText('');
    setShowHighlightModal(false);
    setHighlightInfo(null);
  };

  if (step === 'select') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
        <div className="container mx-auto max-w-4xl">
          <div className="text-center mb-8">
            <h1 className="text-4xl font-bold text-gray-800 mb-4">
              Contract Proposal Generator
            </h1>
            <p className="text-lg text-gray-600">
              Select a government contract to generate AI-powered proposal outlines
            </p>
          </div>

          <Card className="mb-8">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ExternalLink className="h-5 w-5" />
                Custom Contract URL
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-4">
                <Input
                  value={customUrl}
                  onChange={(e) => setCustomUrl(e.target.value)}
                  placeholder="Paste sam.gov contract URL here..."
                  className="flex-1"
                />
                <Button 
                  onClick={() => processContract(customUrl)}
                  disabled={!customUrl.trim() || loading}
                >
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Process'}
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Suggested Contracts
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loading && suggestedContracts.length === 0 ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-8 w-8 animate-spin" />
                  <span className="ml-2">Loading contracts...</span>
                </div>
              ) : (
                <div className="space-y-4">
                  {suggestedContracts.map((contract, index) => (
                    <div
                      key={index}
                      className="border rounded-lg p-4 hover:bg-gray-50 cursor-pointer transition-colors"
                      onClick={() => processContract(contract.url)}
                    >
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <h3 className="font-semibold text-gray-800 mb-2">
                            {contract.title}
                          </h3>
                          <p className="text-sm text-gray-600 mb-2">
                            {contract.url}
                          </p>
                          <Badge variant="outline">Department of Defense</Badge>
                        </div>
                        <Button variant="outline" size="sm">
                          Select
                        </Button>
                      </div>
                    </div>
                  ))}
                  
                  {suggestedContracts.length === 0 && !loading && (
                    <div className="text-center py-8 text-gray-500">
                      No contracts found. Try refreshing or use a custom URL.
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  if (step === 'processing') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <Card className="w-full max-w-md">
          <CardContent className="p-8 text-center">
            <Loader2 className="h-12 w-12 animate-spin mx-auto mb-4 text-blue-600" />
            <h2 className="text-xl font-semibold mb-2">Processing Contract</h2>
            <p className="text-gray-600">
              Analyzing contract details and generating initial proposal outline...
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 p-4">
        <div className="container mx-auto flex justify-between items-center">
          <div>
            <h1 className="text-xl font-semibold">Contract Proposal Generator</h1>
            <p className="text-sm text-gray-600">{session?.contract_url}</p>
          </div>
          <Button variant="outline" onClick={resetApp}>
            New Contract
          </Button>
        </div>
      </div>

      <div className="container mx-auto p-4 grid grid-cols-1 lg:grid-cols-3 gap-6 h-[calc(100vh-100px)]">
        {/* Contract Content Panel */}
        <Card className="lg:col-span-1 overflow-hidden">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Contract Details
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0 h-full">
            <div 
              ref={contractContentRef}
              className="p-4 h-full overflow-auto text-sm whitespace-pre-wrap font-mono bg-gray-50"
              onMouseUp={handleTextSelection}
            >
              {contractContent}
            </div>
          </CardContent>
        </Card>

        {/* Chat Panel */}
        <Card className="lg:col-span-2 flex flex-col">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5" />
              Proposal Assistant
            </CardTitle>
          </CardHeader>
          
          <CardContent className="flex-1 flex flex-col p-0">
            {/* Messages */}
            <div className="flex-1 overflow-auto p-4 space-y-4">
              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`flex ${message.type === 'human' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg p-3 ${
                      message.type === 'human'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    <div className="whitespace-pre-wrap">{message.content}</div>
                    {message.sources && message.sources.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-gray-300">
                        <div className="text-xs text-gray-600 mb-1">Sources:</div>
                        {message.sources.map((source, i) => (
                          <div key={i} className="text-xs bg-gray-200 rounded p-1 mb-1">
                            {source}
                          </div>
                        ))}
                      </div>
                    )}
                    {message.type === 'ai' && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="mt-2 h-6 text-xs"
                        onClick={() => copyToClipboard(message.content)}
                      >
                        <Copy className="h-3 w-3 mr-1" />
                        Copy
                      </Button>
                    )}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="border-t border-gray-200 p-4">
              <div className="flex gap-2">
                <Textarea
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  placeholder="Ask about the contract or request proposal modifications..."
                  className="resize-none"
                  rows={2}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      sendMessage();
                    }
                  }}
                />
                <Button onClick={sendMessage} disabled={!inputMessage.trim()}>
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Highlight Modal */}
      {showHighlightModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <Search className="h-5 w-5" />
                  Text Highlighted
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowHighlightModal(false)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="mb-4">
                <div className="text-sm font-medium mb-2">Selected text:</div>
                <div className="bg-yellow-100 p-2 rounded text-sm">
                  "{highlightedText}"
                </div>
              </div>
              
              <Button
                onClick={() => {
                  handleHighlightQuestion();
                  setShowHighlightModal(false);
                }}
                className="w-full"
              >
                Where does this come from?
              </Button>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Highlight Info Modal */}
      {highlightInfo && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <Card className="w-full max-w-lg">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Source Information</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setHighlightInfo(null)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <Badge variant={highlightInfo.source === 'contract_document' ? 'default' : 'secondary'}>
                    {highlightInfo.source === 'contract_document' ? 'From Contract' : 'AI Generated'}
                  </Badge>
                </div>
                
                <div>
                  <div className="text-sm font-medium mb-2">Explanation:</div>
                  <div className="text-sm text-gray-700">
                    {highlightInfo.explanation}
                  </div>
                </div>
                
                {highlightInfo.context && (
                  <div>
                    <div className="text-sm font-medium mb-2">Context:</div>
                    <div className="bg-gray-100 p-3 rounded text-sm font-mono">
                      {highlightInfo.context}
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}