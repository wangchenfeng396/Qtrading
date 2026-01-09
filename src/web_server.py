from flask import Flask, jsonify, render_template, request
import os
import sys

# Ensure src is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db

app = Flask(__name__, template_folder='templates')

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/equity')
def api_equity():
    env = request.args.get('env', 'live')
    db = get_db(env)
    if not db:
        return jsonify({'error': 'Invalid environment'}), 400
        
    data = db.get_equity_history()
    # Format for Plotly: x=times, y=values
    return jsonify({
        'x': [row[0] for row in data],
        'y': [row[1] for row in data]
    })

@app.route('/api/operations')
def api_operations():
    env = request.args.get('env', 'live')
    db = get_db(env)
    if not db:
        return jsonify({'error': 'Invalid environment'}), 400

    data = db.get_recent_operations()
    return jsonify(data)

def run_server():
    # Run on 0.0.0.0 to be accessible externally if needed, port 5001
    app.run(host='0.0.0.0', port=5001, debug=False)

if __name__ == '__main__':
    run_server()
