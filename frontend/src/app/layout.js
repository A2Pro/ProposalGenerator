import './globals.css';

export const metadata = {
  title: 'Contract Proposal Generator',
  description: 'AI-powered government contract proposal generator',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background font-sans antialiased">
        {children}
      </body>
    </html>
  );
}