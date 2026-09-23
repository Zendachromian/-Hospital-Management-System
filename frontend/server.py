#!/usr/bin/env python3
"""
Frontend Development Server
Serves the Vue.js SPA on port 8080
- Root path "/" serves the landing page
- Path "/app" and other routes serve the main Vue.js app
"""
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import sys

class CORSRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('ETag', f'W/"dynamic-{os.urandom(8).hex()}"')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        # Remove query parameters
        clean_path = self.path.split('?')[0]
        
        # LANDING PAGE at root - serve directly without caching
        if clean_path == '/':
            try:
                with open('templates/landing.html', 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', len(content))
                self.end_headers()
                self.wfile.write(content)
                return
            except Exception as e:
                self.send_error(404, f"Landing page error: {e}")
                return
        
        # APP route - serve index.html directly
        if clean_path.startswith('/app'):
            try:
                with open('templates/index.html', 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', len(content))
                self.end_headers()
                self.wfile.write(content)
                return
            except Exception as e:
                self.send_error(404, f"App page error: {e}")
                return
        
        # Default handler for static files and other routes
        super().do_GET()

if __name__ == '__main__':
    # Change to frontend directory
    frontend_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(frontend_dir)
    
    PORT = 8080
    
    print(f"🎨 Frontend Server Starting...")
    print(f"📁 Serving from: {frontend_dir}")
    print(f"🌐 Landing Page: http://localhost:{PORT}/ (landing.html)")
    print(f"🌐 Application: http://localhost:{PORT}/app (index.html)")
    print(f"🔗 API Backend: http://localhost:5000/api")
    print(f"⏹️  Press Ctrl+C to stop")
    
    server = HTTPServer(('localhost', PORT), CORSRequestHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Frontend server stopped")
        sys.exit(0)

if __name__ == '__main__':
    # Change to frontend directory
    frontend_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(frontend_dir)
    
    PORT = 8080
    
    print(f"🎨 Frontend Server Starting...")
    print(f"📁 Serving from: {frontend_dir}")
    print(f"🌐 Landing Page: http://localhost:{PORT}")
    print(f"🌐 Application: http://localhost:{PORT}/app")
    print(f"🔗 API Backend: http://localhost:5000/api")
    print(f"⏹️  Press Ctrl+C to stop")
    
    server = HTTPServer(('localhost', PORT), CORSRequestHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Frontend server stopped")
        sys.exit(0)
