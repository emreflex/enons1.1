"""Yerel ağ arayüzü: eşleştirme parolası, CSRF ve hız sınırı."""
from collections import defaultdict, deque
import hmac
import secrets
import time
from flask import Flask, jsonify, render_template, request, session
from .plates import REASONS, parse_plate


def secure_equal(left, right):
    # compare_digest(str, str) ASCII dışı hatalı girdide TypeError üretir.
    return hmac.compare_digest(left.encode('utf-8'), right.encode('utf-8'))


def create_app(store, pairing_password, on_new=lambda: None):
    app = Flask(__name__)
    app.secret_key = secrets.token_bytes(32)
    app.config.update(MAX_CONTENT_LENGTH=4096, SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE='Strict')
    attempts = defaultdict(deque)

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    @app.get('/')
    def index():
        session.setdefault('csrf', secrets.token_urlsafe(24))
        return render_template('index.html', authorized=session.get('authorized', False),
                               csrf=session['csrf'], reasons=REASONS)

    @app.post('/api/login')
    def login():
        if not secure_equal(request.form.get('csrf', ''), session.get('csrf', '!')):
            return jsonify(error='Sayfayı yenileyiniz.'), 403
        now = time.monotonic()
        # Toplam anahtar sayısı da sınırlı; rastgele adreslerle belleği büyütmeyiz.
        ip = request.remote_addr or 'local'
        if len(attempts) > 1024:
            attempts.clear()
        history = attempts[ip]
        while history and now - history[0] >= 60:
            history.popleft()
        if len(history) >= 10:
            return jsonify(error='Bir dakika sonra tekrar deneyiniz.'), 429
        history.append(now)
        if not secure_equal(request.form.get('password', ''), pairing_password):
            return jsonify(error='Eşleştirme parolası yanlış.'), 401
        session['authorized'] = True
        return jsonify(ok=True)

    @app.post('/api/requests')
    def submit():
        if not session.get('authorized'):
            return jsonify(error='Önce eşleştirme yapınız.'), 401
        if not secure_equal(request.form.get('csrf', ''), session.get('csrf', '!')):
            return jsonify(error='Sayfayı yenileyiniz.'), 403
        if time.monotonic() - session.get('last_submit', -100) < 2:
            return jsonify(error='Yeni istek için iki saniye bekleyiniz.'), 429
        try:
            plate = ' '.join(parse_plate(request.form.get('plate', '')))
            reason = request.form.get('reason', '')
            if reason not in REASONS:
                raise ValueError('Geçersiz anons sebebi.')
            request_id = store.add(plate, reason)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        session['last_submit'] = time.monotonic()
        on_new()
        return jsonify(ok=True, id=request_id), 201

    return app
