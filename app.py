from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import json, os, uuid, hashlib, re, random, base64
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'cardhub_community_2025_xK9z_v4'
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024

BASE = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIRS = {
    'thumbnails':  os.path.join(BASE, 'static', 'uploads', 'thumbnails'),
    'avatars':     os.path.join(BASE, 'static', 'uploads', 'avatars'),
    'backgrounds': os.path.join(BASE, 'static', 'uploads', 'backgrounds'),
    'logos':       os.path.join(BASE, 'static', 'uploads', 'logos'),
    'general':     os.path.join(BASE, 'static', 'uploads'),
}
for d in UPLOAD_DIRS.values():
    os.makedirs(d, exist_ok=True)
os.makedirs(os.path.join(BASE, 'data'), exist_ok=True)

# ─── JSON DB ─────────────────────────────────────────
def db_path(name): return os.path.join(BASE, 'data', name + '.json')

def load(name, default=None):
    if default is None: default = {}
    p = db_path(name)
    if not os.path.exists(p): save(name, default); return default
    try:
        with open(p) as f: return json.load(f)
    except: return default

def save(name, data):
    with open(db_path(name), 'w') as f: json.dump(data, f, indent=2)

def init_db():
    for n, d in [
        ('users',{}), ('community_templates',{}),
        ('likes',{}), ('saves',{}), ('comments',{}),
        ('ratings',{}), ('views',{}), ('saved_cards',[]),
        ('brand_kits',[]), ('rsvps',[]),
        ('follows',{}),        # {follower_id: [following_id,...]}
        ('follow_requests',{}),# {target_user_id: [requester_id,...]}
        ('posts',{}),          # {post_id: {...post data}}
        ('post_likes',{}),     # {post_id: [user_ids]}
        ('post_comments',{}),  # {post_id: [{...}]}
        ('post_saves',{}),     # {user_id: [post_ids]}
    ]:
        p = db_path(n)
        if not os.path.exists(p): save(n, d)
init_db()

# ─── Helpers ─────────────────────────────────────────
def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def now_str(): return datetime.now().strftime('%b %d, %Y')
def now_full(): return datetime.now().strftime('%b %d, %Y %H:%M')

def current_user():
    uid = session.get('uid')
    if not uid: return None
    return load('users').get(uid)

def login_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if not session.get('uid'):
            return redirect('/login?next=' + request.path)
        return f(*a, **kw)
    return dec

def save_file(file, folder='general'):
    if not file or not file.filename: return ''
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in ['jpg','jpeg','png','gif','webp','svg']: return ''
    fname = str(uuid.uuid4()) + '.' + ext
    path = UPLOAD_DIRS.get(folder, UPLOAD_DIRS['general'])
    file.save(os.path.join(path, fname))
    sub = '' if folder == 'general' else folder + '/'
    return f'/static/uploads/{sub}{fname}'

def get_follower_count(uid):
    follows = load('follows', {})
    return sum(1 for followers in follows.values() if uid in followers)

def get_following_ids(uid):
    follows = load('follows', {})
    return follows.get(uid, [])

def is_following(follower_id, target_id):
    return target_id in load('follows', {}).get(follower_id, [])

def has_follow_request(requester_id, target_id):
    return requester_id in load('follow_requests', {}).get(target_id, [])

def user_template_count(uid):
    community = load('community_templates', {})
    return sum(1 for t in community.values() if t.get('uploader_id') == uid)

def can_hd_download(user):
    """HD unlocked for: 3+ uploads OR premium"""
    if not user: return False
    if user.get('is_premium'): return True
    return user_template_count(user['id']) >= 3

def earns_star(uid):
    """Yellow star after 100 followers OR 50+ uploads"""
    followers = get_follower_count(uid)
    uploads = user_template_count(uid)
    return followers >= 100 or uploads >= 50

# ─── Built-in Templates ──────────────────────────────
BUILTIN = [
    {"id":"birthday-gold","title":"Golden Birthday","category":"Birthday","tags":["birthday"],"bg":"linear-gradient(135deg,#b8860b 0%,#ffd700 50%,#b8860b 100%)","text_color":"#1a1400","default_title":"Birthday Bash!","default_subtitle":"You're invited to celebrate","default_details":"Saturday, 8 PM • Mumbai","emoji":"🎂","builtin":True,"elements":[]},
    {"id":"wedding-blush","title":"Blush Wedding","category":"Wedding","tags":["wedding"],"bg":"linear-gradient(135deg,#c9748b 0%,#e8a0b4 50%,#f5c6d0 100%)","text_color":"#fff","default_title":"Together Forever","default_subtitle":"Join us as we celebrate our union","default_details":"December 12 • The Grand Hall","emoji":"💍","builtin":True,"elements":[]},
    {"id":"party-neon","title":"Neon Party","category":"Party","tags":["party"],"bg":"linear-gradient(135deg,#1a0533 0%,#4a0080 50%,#1a0533 100%)","text_color":"#fff","default_title":"Let's Party!","default_subtitle":"You're officially invited","default_details":"Friday Night • Rooftop Lounge","emoji":"🎉","builtin":True,"elements":[]},
    {"id":"graduation-navy","title":"Grand Graduation","category":"Graduation","tags":["graduation"],"bg":"linear-gradient(135deg,#0d1b4b 0%,#1a3080 50%,#0d1b4b 100%)","text_color":"#fff","default_title":"I Did It!","default_subtitle":"Please join me for my graduation","default_details":"June 15 • University Hall","emoji":"🎓","builtin":True,"elements":[]},
    {"id":"baby-shower-mint","title":"Mint Baby Shower","category":"Baby Shower","tags":["baby"],"bg":"linear-gradient(135deg,#a8e6cf 0%,#dcedc1 50%,#a8e6cf 100%)","text_color":"#2d6a4f","default_title":"Baby on the Way!","default_subtitle":"Join us for a baby shower","default_details":"Sunday Brunch • Our Home","emoji":"👶","builtin":True,"elements":[]},
    {"id":"anniversary-rose","title":"Rose Anniversary","category":"Anniversary","tags":["anniversary"],"bg":"linear-gradient(135deg,#8b1a2e 0%,#c0392b 50%,#8b1a2e 100%)","text_color":"#fff","default_title":"25 Years Together","default_subtitle":"Silver Anniversary Celebration","default_details":"October 20 • The Rose Garden","emoji":"🌹","builtin":True,"elements":[]},
    {"id":"business-slate","title":"Business Slate","category":"Business","tags":["business"],"bg":"linear-gradient(135deg,#1c2340 0%,#2d3561 50%,#1c2340 100%)","text_color":"#e8eaf6","default_title":"Product Launch","default_subtitle":"You're invited to an exclusive event","default_details":"Monday, 6 PM • Conference Hall A","emoji":"💼","builtin":True,"elements":[]},
    {"id":"diwali-gold","title":"Diwali Glow","category":"Festival","tags":["diwali"],"bg":"linear-gradient(135deg,#4a1942 0%,#c0392b 40%,#f39c12 100%)","text_color":"#fff","default_title":"Happy Diwali!","default_subtitle":"Light up the night with us","default_details":"Oct 31 • Our Home","emoji":"🪔","builtin":True,"elements":[]},
    {"id":"ocean-blue","title":"Ocean Breeze","category":"Birthday","tags":["ocean"],"bg":"linear-gradient(135deg,#023e8a 0%,#0077b6 50%,#00b4d8 100%)","text_color":"#fff","default_title":"Beach Party!","default_subtitle":"Sun, sand, and celebration","default_details":"Sunday, 4 PM • Juhu Beach","emoji":"🌊","builtin":True,"elements":[]},
    {"id":"christmas-green","title":"Christmas Cheer","category":"Holiday","tags":["christmas"],"bg":"linear-gradient(135deg,#1b4332 0%,#2d6a4f 50%,#1b4332 100%)","text_color":"#fff","default_title":"Season's Greetings","default_subtitle":"Warmth and joy to you and yours","default_details":"December 25 • Our Home","emoji":"🎄","builtin":True,"elements":[]},
    {"id":"retro-sunset","title":"Retro Sunset","category":"Party","tags":["retro"],"bg":"linear-gradient(135deg,#ff6b35 0%,#f7c59f 50%,#ff6b35 100%)","text_color":"#1a0a00","default_title":"Sunset Soirée","default_subtitle":"Come celebrate with us","default_details":"Saturday Dusk • The Terrace","emoji":"🌅","builtin":True,"elements":[]},
    {"id":"minimal-white","title":"Minimal White","category":"Business","tags":["minimal"],"bg":"linear-gradient(135deg,#f8f9fa 0%,#e9ecef 50%,#f8f9fa 100%)","text_color":"#212529","default_title":"You're Invited","default_subtitle":"An exclusive gathering","default_details":"Friday, 7 PM • The Venue","emoji":"✨","builtin":True,"elements":[]},
]

# AI suggestions per category
AI_MESSAGES = {
    'birthday': ["🎂 Wishing you a day as brilliant as your smile! Join us for cake, laughter, and memories that last forever.","Another year of adventures awaits — let's celebrate the amazing soul you are! Don't miss the bash!","Today we put the spotlight on YOU. Come celebrate the one who lights up every room. It's going to be magical!"],
    'wedding': ["💍 Two hearts, one beautiful journey. Please join us as we say 'I do' and begin forever together.","With overflowing joy and love, we invite you to witness our union and share in our happiness.","Love chose us. Now we choose to celebrate it with you. Please join us for the most beautiful day of our lives."],
    'party': ["🎉 Good music, great people, legendary night. You're officially on the VIP guest list — don't miss out!","The night is young and so are we. Come party with us — it's going to be absolutely unforgettable!","Warning: extreme fun ahead. Attendance is basically mandatory. See you on the dance floor!"],
    'graduation': ["🎓 I moved my tassel — now let's move the party! Join me to celebrate this incredible milestone.","Years of hard work, late nights, and determination paid off. Time to celebrate! You're invited.","Diploma: secured. Future: bright. Party: incoming. RSVP now to celebrate this milestone with me!"],
    'anniversary': ["🌹 Years of love, laughter, and cherished memories. Join us as we celebrate the beautiful journey we've shared.","Every year with you is a gift. We're celebrating this milestone and would love you to be part of our joy.","To love, to laughter, to happily ever after — please join us as we mark another beautiful year together."],
    'baby shower': ["👶 A little one is on the way and we couldn't be more excited! Join us to celebrate this beautiful new chapter.","Tiny fingers, tiny toes, a whole lot of love — come shower the mama-to-be with joy and blessings!","The most precious gift is almost here. Join us to welcome the newest little star into the world!"],
    'festival': ["🪔 Let your home be filled with the glow of lights and the warmth of togetherness. Join us in celebration!","Celebrate the festival of light, love, and new beginnings with us. Your presence makes it brighter!","Warmth, laughter, and togetherness — that's what we're celebrating. Come join the festivities!"],
    'holiday': ["🎄 May your season be wrapped in joy, laughter, and the company of those you love. Join us for the celebration!","The most wonderful time of year is even more wonderful with you. We'd love to have you with us!","Celebrate the magic of the season with family, friends, and festive cheer. See you there!"],
    'business': ["💼 You're exclusively invited to an evening of innovation, inspiration, and industry leadership. Reserve your seat.","Join the brightest minds in the industry for an unmissable evening of networking and excellence.","An exclusive gathering of visionaries and innovators. We're honoured to invite you to be part of this milestone."],
}

def all_templates():
    community = load('community_templates', {})
    result = {}
    for t in BUILTIN:
        result[t['id']] = t
    for tid, t in community.items():
        result[tid] = t
    return result

def get_template(tid):
    return all_templates().get(tid)

# ══════════════════════════════════════════════════════
#  PAGE ROUTES
# ══════════════════════════════════════════════════════

@app.route('/')
def home():
    user = current_user()
    tmpls = all_templates()
    users = load('users', {})
    likes = load('likes', {})
    views = load('views', {})
    tmpl_list = list(tmpls.values())

    def score(t): return len(likes.get(t['id'],[])) * 3 + views.get(t['id'],0)
    trending = sorted(tmpl_list, key=score, reverse=True)[:8]
    latest_community = sorted([t for t in tmpl_list if not t.get('builtin')],
                              key=lambda t: t.get('created_at',''), reverse=True)[:8]
    builtin_featured = [t for t in BUILTIN][:4]
    premium_tmpls = [t for t in tmpl_list if t.get('is_premium')][:4]
    uploaders = sorted([u for u in users.values() if u.get('role') in ['uploader','admin']],
                       key=lambda u: get_follower_count(u['id']), reverse=True)[:6]
    return render_template('home.html', user=user, trending=trending,
        latest_community=latest_community, builtin_featured=builtin_featured,
        premium_tmpls=premium_tmpls, uploaders=uploaders,
        users=users, likes=likes, views=views,
        get_follower_count=get_follower_count, earns_star=earns_star)

@app.route('/explore')
def explore():
    user = current_user()
    q = request.args.get('q','').lower().strip()
    cat = request.args.get('cat','All')
    sort = request.args.get('sort','newest')
    tmpls = all_templates()
    users = load('users', {})
    likes = load('likes', {})
    views = load('views', {})
    tmpl_list = list(tmpls.values())
    cats = ['All'] + sorted(list({t.get('category','General') for t in tmpl_list}))
    if q:
        tmpl_list = [t for t in tmpl_list if q in t.get('title',t.get('name','')).lower()
                     or q in users.get(t.get('uploader_id',''),{}).get('username','').lower()
                     or q in t.get('category','').lower()]
    if cat != 'All': tmpl_list = [t for t in tmpl_list if t.get('category') == cat]
    if sort == 'newest': tmpl_list.sort(key=lambda t: t.get('created_at',''), reverse=True)
    elif sort == 'popular': tmpl_list.sort(key=lambda t: len(likes.get(t['id'],[])), reverse=True)
    elif sort == 'trending': tmpl_list.sort(key=lambda t: len(likes.get(t['id'],[]))*3+views.get(t['id'],0), reverse=True)
    return render_template('explore.html', user=user, templates=tmpl_list,
        users=users, likes=likes, views=views, q=q, cat=cat, sort=sort, cats=cats)

@app.route('/template/<tid>')
def view_template(tid):
    user = current_user()
    t = get_template(tid)
    if not t: return redirect('/explore')
    views = load('views', {})
    views[tid] = views.get(tid,0) + 1
    save('views', views)
    users = load('users', {})
    uploader = users.get(t.get('uploader_id',''), {})
    likes = load('likes', {})
    saves = load('saves', {})
    comments_data = load('comments', {})
    ratings = load('ratings', {})
    tid_comments = comments_data.get(tid, [])
    for c in tid_comments:
        c['_user'] = users.get(c['user_id'], {'username':'Unknown','avatar':''})
    avg_rating = 0
    if ratings.get(tid):
        avg_rating = round(sum(ratings[tid].values()) / len(ratings[tid]), 1)
    uid = user['id'] if user else ''
    is_subscribed = bool(user and user.get('is_premium'))
    related = [v for k,v in all_templates().items() if v.get('category') == t.get('category') and k != tid][:4]
    uploader_star = earns_star(uploader.get('id','')) if uploader.get('id') else False
    return render_template('template_view.html', user=user, t=t,
        uploader=uploader, like_count=len(likes.get(tid,[])),
        view_count=views.get(tid,0), is_liked=uid in likes.get(tid,[]),
        is_saved=tid in saves.get(uid,[]), comments=tid_comments,
        avg_rating=avg_rating, user_rating=ratings.get(tid,{}).get(uid,0),
        is_subscribed=is_subscribed, related=related, users=users,
        likes=likes, views=views, uploader_star=uploader_star,
        can_hd=can_hd_download(user))

@app.route('/editor/<tid>')
@login_required
def editor(tid):
    user = current_user()
    t = get_template(tid)
    if not t: return redirect('/explore')

    # If editing a saved card, merge its data back
    card_id = request.args.get('card_id')
    saved_card = None
    if card_id:
        cards = load('saved_cards', [])
        saved_card = next((c for c in cards if c['id'] == card_id and c.get('user_id') == user['id']), None)
        if saved_card:
            # Merge saved card data into template for editor
            t = dict(t)
            t['elements'] = saved_card.get('elements', t.get('elements', []))
            t['bg'] = saved_card.get('bg', t.get('bg',''))
            t['bg_image'] = saved_card.get('bg_image','')
            t['text_color'] = saved_card.get('text_color', t.get('text_color','#fff'))
            t['_saved_card_id'] = card_id

    brand_kits = load('brand_kits', [])
    is_owner = t.get('uploader_id') == user['id']
    is_subscribed = user.get('is_premium', False)
    return render_template('editor.html', user=user, template=t,
        brand_kits=brand_kits, is_owner=is_owner,
        is_subscribed=is_subscribed, saved_card=saved_card)

@app.route('/profile/<username>')
def profile(username):
    user = current_user()
    users = load('users', {})
    prof = next((u for u in users.values() if u['username'] == username), None)
    if not prof: return redirect('/')

    # Privacy check
    is_own = user and user['id'] == prof['id']
    follower_ids = get_following_ids(user['id'] if user else '')
    is_following_prof = prof['id'] in follower_ids
    privacy = prof.get('profile_privacy', 'public')
    can_view_full = is_own or privacy == 'public' or is_following_prof

    community = load('community_templates', {})
    user_tmpls = sorted([t for t in community.values() if t.get('uploader_id') == prof['id']],
                        key=lambda t: t.get('created_at',''), reverse=True)
    likes = load('likes', {})
    views = load('views', {})
    saves = load('saves', {})
    all_t = all_templates()
    saved_ids = saves.get(prof['id'], [])
    saved_tmpls = [all_t[tid] for tid in saved_ids if tid in all_t]

    total_likes = sum(len(likes.get(t['id'],[])) for t in user_tmpls)
    total_views = sum(views.get(t['id'],0) for t in user_tmpls)
    total_dl = sum(t.get('downloads',0) for t in user_tmpls)
    follower_count = get_follower_count(prof['id'])
    following_count = len(get_following_ids(prof['id']))

    has_request = user and has_follow_request(user['id'], prof['id'])
    star = earns_star(prof['id'])
    can_hd = can_hd_download(user)

    # Posts
    posts_db = load('posts', {})
    post_likes = load('post_likes', {})
    post_comments = load('post_comments', {})
    post_saves_db = load('post_saves', {})
    user_posts = sorted(
        [p for p in posts_db.values() if p['user_id'] == prof['id']],
        key=lambda p: p.get('created_at',''), reverse=True
    )
    my_saved_posts = post_saves_db.get(user['id'] if user else '', [])

    return render_template('profile.html', user=user, prof=prof,
        user_tmpls=user_tmpls, saved_tmpls=saved_tmpls,
        total_likes=total_likes, total_views=total_views, total_dl=total_dl,
        likes=likes, views=views, users=users,
        follower_count=follower_count, following_count=following_count,
        is_following_prof=is_following_prof, can_view_full=can_view_full,
        has_request=has_request, privacy=privacy, star=star, can_hd=can_hd,
        user_posts=user_posts, post_likes=post_likes, post_comments=post_comments,
        my_saved_posts=my_saved_posts)

@app.route('/community')
def community_page():
    user = current_user()
    users = load('users', {})
    follows = load('follows', {})
    my_following = get_following_ids(user['id'] if user else '')

    q = request.args.get('q','').lower().strip()
    all_users = list(users.values())
    if q:
        all_users = [u for u in all_users if q in u['username'].lower() or q in u.get('bio','').lower()]

    # Sort by followers desc
    all_users.sort(key=lambda u: get_follower_count(u['id']), reverse=True)

    return render_template('community.html', user=user, all_users=all_users,
        my_following=my_following, get_follower_count=get_follower_count,
        earns_star=earns_star, q=q,
        user_template_count=user_template_count)

@app.route('/upload')
@login_required
def upload_page():
    user = current_user()
    return render_template('upload.html', user=user)

@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user()
    community = load('community_templates', {})
    likes = load('likes', {})
    views = load('views', {})
    my_t = sorted([t for t in community.values() if t.get('uploader_id') == user['id']],
                  key=lambda t: t.get('created_at',''), reverse=True)
    stats = {
        'templates': len(my_t),
        'total_likes': sum(len(likes.get(t['id'],[])) for t in my_t),
        'total_views': sum(views.get(t['id'],0) for t in my_t),
        'total_downloads': sum(t.get('downloads',0) for t in my_t),
        'followers': get_follower_count(user['id']),
    }
    hd_unlocked = can_hd_download(user)
    uploads_to_hd = max(0, 3 - len(my_t))
    star = earns_star(user['id'])
    return render_template('dashboard.html', user=user, my_t=my_t,
        stats=stats, likes=likes, views=views,
        hd_unlocked=hd_unlocked, uploads_to_hd=uploads_to_hd, star=star)

@app.route('/my-cards')
@login_required
def my_cards():
    user = current_user()
    cards = load('saved_cards', [])
    my = [c for c in cards if c.get('user_id') == user['id']]
    all_t = all_templates()
    return render_template('my_cards.html', user=user, cards=my, all_templates=all_t)

@app.route('/premium')
def premium_page():
    return render_template('premium.html', user=current_user())

@app.route('/settings')
@login_required
def settings_page():
    return render_template('settings.html', user=current_user())

@app.route('/brand-kit')
@login_required
def brand_kit_page():
    user = current_user()
    kits = [k for k in load('brand_kits',[]) if k.get('user_id') == user['id']]
    return render_template('brand_kit.html', user=user, kits=kits)

@app.route('/login')
def login_page():
    if session.get('uid'): return redirect('/')
    return render_template('auth.html', mode='login')

@app.route('/register')
def register_page():
    if session.get('uid'): return redirect('/')
    return render_template('auth.html', mode='register')

@app.route('/rsvp/<card_id>')
def rsvp_page(card_id):
    cards = load('saved_cards', [])
    card = next((c for c in cards if c['id'] == card_id), None)
    rsvps = [r for r in load('rsvps',[]) if r.get('card_id') == card_id]
    return render_template('rsvp.html', user=current_user(), card=card, rsvps=rsvps, card_id=card_id)

# ══════════════════════════════════════════════════════
#  AUTH APIs
# ══════════════════════════════════════════════════════

@app.route('/api/register', methods=['POST'])
def api_register():
    d = request.get_json()
    username = d.get('username','').strip().lower()
    email = d.get('email','').strip().lower()
    password = d.get('password','')
    role = d.get('role','downloader')
    if not re.match(r'^[a-z0-9_]{3,20}$', username):
        return jsonify({'error':'Username: 3-20 chars, letters/numbers/underscore'}), 400
    if len(password) < 6:
        return jsonify({'error':'Password must be 6+ characters'}), 400
    users = load('users', {})
    if any(u['username'] == username for u in users.values()):
        return jsonify({'error':'Username already taken'}), 400
    if any(u['email'] == email for u in users.values()):
        return jsonify({'error':'Email already registered'}), 400
    uid = str(uuid.uuid4())
    users[uid] = {
        'id':uid, 'username':username, 'email':email, 'password':hash_pw(password),
        'role':role, 'bio':'', 'website':'', 'contact':'',
        'avatar':'', 'display_name':'', 'logo_url':'',
        'watermark_text':f'@{username}', 'watermark_type':'text',
        'is_premium':False, 'created_at':now_str(), 'profile_privacy':'public',
    }
    save('users', users)
    session['uid'] = uid
    return jsonify({'success':True, 'username':username, 'role':role})

@app.route('/api/login', methods=['POST'])
def api_login():
    d = request.get_json()
    ident = d.get('identifier','').strip().lower()
    users = load('users', {})
    u = next((u for u in users.values()
               if (u['username']==ident or u['email']==ident)
               and u['password']==hash_pw(d.get('password',''))), None)
    if not u: return jsonify({'error':'Invalid username or password'}), 401
    session['uid'] = u['id']
    return jsonify({'success':True, 'username':u['username'], 'role':u['role']})

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear(); return jsonify({'success':True})

@app.route('/api/change-role', methods=['POST'])
@login_required
def api_change_role():
    user = current_user()
    d = request.get_json()
    new_role = d.get('role')
    if new_role not in ['uploader','downloader']:
        return jsonify({'error':'Invalid role'}), 400
    users = load('users', {})
    users[user['id']]['role'] = new_role
    save('users', users)
    return jsonify({'success':True, 'role':new_role})

# ══════════════════════════════════════════════════════
#  FOLLOW SYSTEM
# ══════════════════════════════════════════════════════

@app.route('/api/follow/<target_id>', methods=['POST'])
@login_required
def api_follow(target_id):
    user = current_user()
    if user['id'] == target_id:
        return jsonify({'error':"Can't follow yourself"}), 400
    users = load('users', {})
    target = users.get(target_id)
    if not target: return jsonify({'error':'User not found'}), 404

    follows = load('follows', {})
    my_following = follows.get(user['id'], [])

    # If already following -> unfollow
    if target_id in my_following:
        my_following.remove(target_id)
        follows[user['id']] = my_following
        save('follows', follows)
        return jsonify({'success':True, 'action':'unfollowed', 'followers': get_follower_count(target_id)})

    # Check privacy
    privacy = target.get('profile_privacy', 'public')
    if privacy == 'private':
        # Send follow request instead
        requests = load('follow_requests', {})
        if user['id'] not in requests.get(target_id, []):
            requests.setdefault(target_id, []).append(user['id'])
            save('follow_requests', requests)
        return jsonify({'success':True, 'action':'requested'})

    # Public profile — follow directly
    my_following.append(target_id)
    follows[user['id']] = my_following
    save('follows', follows)
    return jsonify({'success':True, 'action':'followed', 'followers': get_follower_count(target_id)})

@app.route('/api/follow-request/<requester_id>/<action>', methods=['POST'])
@login_required
def api_handle_request(requester_id, action):
    user = current_user()
    requests = load('follow_requests', {})
    my_requests = requests.get(user['id'], [])
    if requester_id not in my_requests:
        return jsonify({'error':'No such request'}), 404
    my_requests.remove(requester_id)
    requests[user['id']] = my_requests
    save('follow_requests', requests)
    if action == 'accept':
        follows = load('follows', {})
        follows.setdefault(requester_id, []).append(user['id'])
        save('follows', follows)
        return jsonify({'success':True, 'action':'accepted'})
    return jsonify({'success':True, 'action':'declined'})

@app.route('/api/follow-requests')
@login_required
def api_get_requests():
    user = current_user()
    users = load('users', {})
    requests = load('follow_requests', {})
    my_reqs = requests.get(user['id'], [])
    result = [{'id':uid,'username':users.get(uid,{}).get('username','?'),'avatar':users.get(uid,{}).get('avatar','')} for uid in my_reqs]
    return jsonify(result)

# ══════════════════════════════════════════════════════
#  COMMUNITY TEMPLATE APIs
# ══════════════════════════════════════════════════════

@app.route('/api/upload-template', methods=['POST'])
@login_required
def api_upload_template():
    user = current_user()
    name = request.form.get('name','').strip()
    if not name: return jsonify({'error':'Name required'}), 400
    thumb_url = save_file(request.files.get('thumbnail'), 'thumbnails')
    tid = str(uuid.uuid4())
    community = load('community_templates', {})
    community[tid] = {
        'id':tid, 'name':name, 'title':name,
        'category':request.form.get('category','General'),
        'description':request.form.get('description',''),
        'bg':request.form.get('bg','linear-gradient(135deg,#1a1a2e,#4a0080)'),
        'text_color':request.form.get('text_color','#ffffff'),
        'elements':json.loads(request.form.get('elements','[]')),
        'thumbnail':thumb_url,
        'watermark_text':request.form.get('watermark_text', user.get('watermark_text','')),
        'watermark_logo':user.get('logo_url',''),
        'uploader_id':user['id'],
        'is_premium':request.form.get('is_premium')=='true',
        'downloads':0, 'created_at':now_str(), 'builtin':False,
    }
    save('community_templates', community)
    return jsonify({'success':True, 'id':tid})

@app.route('/api/delete-template/<tid>', methods=['DELETE'])
@login_required
def api_delete_template(tid):
    user = current_user()
    community = load('community_templates', {})
    t = community.get(tid)
    if not t: return jsonify({'error':'Not found'}), 404
    if t['uploader_id'] != user['id'] and user.get('role') != 'admin':
        return jsonify({'error':'Forbidden'}), 403
    del community[tid]; save('community_templates', community)
    return jsonify({'success':True})

@app.route('/api/download/<tid>', methods=['POST'])
def api_download(tid):
    user = current_user()
    t = get_template(tid)
    if not t: return jsonify({'error':'Not found'}), 404
    if t.get('is_premium') and (not user or not user.get('is_premium')):
        return jsonify({'error':'Premium required'}), 403
    if not t.get('builtin'):
        community = load('community_templates', {})
        if tid in community:
            community[tid]['downloads'] = community[tid].get('downloads',0) + 1
            save('community_templates', community)
    remove_wm = bool(user and user.get('is_premium'))
    hd = can_hd_download(user)
    return jsonify({'success':True, 'remove_watermark':remove_wm, 'hd':hd})

# ══════════════════════════════════════════════════════
#  ENGAGEMENT
# ══════════════════════════════════════════════════════

@app.route('/api/like/<tid>', methods=['POST'])
@login_required
def api_like(tid):
    user = current_user()
    likes = load('likes', {})
    lst = likes.get(tid, [])
    if user['id'] in lst: lst.remove(user['id']); liked=False
    else: lst.append(user['id']); liked=True
    likes[tid] = lst; save('likes', likes)
    return jsonify({'success':True, 'liked':liked, 'count':len(lst)})

@app.route('/api/save/<tid>', methods=['POST'])
@login_required
def api_save_template(tid):
    user = current_user()
    saves = load('saves', {})
    lst = saves.get(user['id'], [])
    if tid in lst: lst.remove(tid); saved=False
    else: lst.append(tid); saved=True
    saves[user['id']] = lst; save('saves', saves)
    return jsonify({'success':True, 'saved':saved})

@app.route('/api/comment/<tid>', methods=['POST'])
@login_required
def api_comment(tid):
    user = current_user()
    text = request.get_json().get('text','').strip()
    if not text or len(text) > 500: return jsonify({'error':'1-500 chars'}), 400
    comments = load('comments', {})
    cid = str(uuid.uuid4())
    c = {'id':cid, 'tid':tid, 'user_id':user['id'], 'text':text, 'created_at':now_str()}
    comments.setdefault(tid, []).append(c); save('comments', comments)
    return jsonify({'success':True, 'comment':{**c,'_user':{'username':user['username'],'avatar':user.get('avatar','')}}})

@app.route('/api/delete-comment/<tid>/<cid>', methods=['DELETE'])
@login_required
def api_delete_comment(tid, cid):
    user = current_user()
    comments = load('comments', {})
    t = get_template(tid) or {}
    lst = comments.get(tid, [])
    c = next((x for x in lst if x['id']==cid), None)
    if not c: return jsonify({'error':'Not found'}), 404
    if c['user_id'] != user['id'] and t.get('uploader_id') != user['id']:
        return jsonify({'error':'Forbidden'}), 403
    comments[tid] = [x for x in lst if x['id']!=cid]
    save('comments', comments)
    return jsonify({'success':True})

@app.route('/api/rate/<tid>', methods=['POST'])
@login_required
def api_rate(tid):
    user = current_user()
    stars = int(request.get_json().get('stars',0))
    if not 1 <= stars <= 5: return jsonify({'error':'1-5'}), 400
    ratings = load('ratings', {})
    ratings.setdefault(tid, {})[user['id']] = stars; save('ratings', ratings)
    avg = round(sum(ratings[tid].values())/len(ratings[tid]),1)
    return jsonify({'success':True, 'avg':avg, 'count':len(ratings[tid])})

# ══════════════════════════════════════════════════════
#  AI TEXT (uses real Anthropic API via in-app fetch)
# ══════════════════════════════════════════════════════

@app.route('/api/ai-text', methods=['POST'])
def api_ai_text():
    d = request.get_json()
    cat = (d.get('category','') or d.get('theme','')).lower()
    extra_context = d.get('context','')

    # First try real AI via claude
    try:
        import urllib.request
        prompt = f"""Generate 3 creative, engaging invitation card messages for a '{cat}' themed card.
{f'Additional context: {extra_context}' if extra_context else ''}
Each message should be warm, enthusiastic, and 1-3 sentences.
Return ONLY a JSON array of 3 strings, no other text. Example: ["msg1","msg2","msg3"]"""

        payload = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 400,
            "messages": [{"role":"user","content":prompt}]
        }).encode()

        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=payload,
            headers={'Content-Type':'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            result = json.loads(resp.read())
            text = result['content'][0]['text'].strip()
            suggestions = json.loads(text)
            if isinstance(suggestions, list) and len(suggestions):
                return jsonify({'suggestions': suggestions[:3], 'ai': True})
    except Exception:
        pass

    # Fallback to built-in messages
    key = next((k for k in AI_MESSAGES if k in cat), 'party')
    msgs = AI_MESSAGES.get(key, AI_MESSAGES['birthday'])[:]
    random.shuffle(msgs)
    return jsonify({'suggestions': msgs[:3], 'ai': False})

# ══════════════════════════════════════════════════════
#  CARD EDITOR APIs
# ══════════════════════════════════════════════════════

@app.route('/api/save-card', methods=['POST'])
@login_required
def api_save_card():
    user = current_user()
    data = request.get_json()
    cards = load('saved_cards', [])
    card_id = data.get('id') or str(uuid.uuid4())
    card = {**data, 'id':card_id, 'user_id':user['id'], 'saved_at':now_str()}
    idx = next((i for i,c in enumerate(cards) if c['id']==card_id and c.get('user_id')==user['id']), None)
    if idx is not None: cards[idx] = card
    else: cards.append(card)
    save('saved_cards', cards)
    return jsonify({'success':True, 'id':card_id})

@app.route('/api/delete-card/<card_id>', methods=['DELETE'])
@login_required
def api_delete_card(card_id):
    user = current_user()
    cards = [c for c in load('saved_cards',[]) if not (c['id']==card_id and c.get('user_id')==user['id'])]
    save('saved_cards', cards)
    return jsonify({'success':True})

@app.route('/api/upload-image', methods=['POST'])
@login_required
def api_upload_image():
    if 'image' not in request.files: return jsonify({'error':'No file'}), 400
    url = save_file(request.files['image'], 'backgrounds')
    if not url: return jsonify({'error':'Invalid file'}), 400
    return jsonify({'url':url})

@app.route('/api/upload-avatar', methods=['POST'])
@login_required
def api_upload_avatar():
    user = current_user()
    url = save_file(request.files.get('avatar'), 'avatars')
    if not url: return jsonify({'error':'Invalid file'}), 400
    users = load('users', {})
    users[user['id']]['avatar'] = url; save('users', users)
    return jsonify({'success':True, 'url':url})

@app.route('/api/upload-logo', methods=['POST'])
@login_required
def api_upload_logo():
    user = current_user()
    url = save_file(request.files.get('logo'), 'logos')
    if not url: return jsonify({'error':'Invalid file'}), 400
    users = load('users', {})
    users[user['id']]['logo_url'] = url
    users[user['id']]['watermark_type'] = 'logo'
    save('users', users)
    return jsonify({'success':True, 'url':url})

@app.route('/api/update-profile', methods=['POST'])
@login_required
def api_update_profile():
    user = current_user()
    users = load('users', {})
    d = request.get_json() or {}
    for f in ['bio','website','contact','watermark_text','display_name','profile_privacy']:
        if f in d: users[user['id']][f] = d[f]
    save('users', users)
    return jsonify({'success':True})

@app.route('/api/subscribe', methods=['POST'])
@login_required
def api_subscribe():
    user = current_user()
    users = load('users', {})
    users[user['id']]['is_premium'] = True; save('users', users)
    return jsonify({'success':True})

@app.route('/api/brand-kit', methods=['POST'])
@login_required
def api_brand_kit():
    user = current_user()
    d = request.get_json()
    kits = load('brand_kits', [])
    kit_id = d.get('id') or str(uuid.uuid4())
    kit = {**d, 'id':kit_id, 'user_id':user['id'], 'created_at':now_str()}
    idx = next((i for i,k in enumerate(kits) if k['id']==kit_id), None)
    if idx is not None: kits[idx] = kit
    else: kits.append(kit)
    save('brand_kits', kits)
    return jsonify({'success':True, 'kit':kit})

@app.route('/api/brand-kit/<kit_id>', methods=['DELETE'])
@login_required
def api_delete_brand_kit(kit_id):
    user = current_user()
    kits = [k for k in load('brand_kits',[]) if not (k['id']==kit_id and k.get('user_id')==user['id'])]
    save('brand_kits', kits)
    return jsonify({'success':True})

@app.route('/api/rsvp', methods=['POST'])
def api_rsvp():
    d = request.get_json()
    rsvps = load('rsvps', [])
    rsvps.append({**d, 'id':str(uuid.uuid4()), 'submitted_at':now_str()})
    save('rsvps', rsvps)
    return jsonify({'success':True})

@app.route('/api/search')
def api_search():
    q = request.args.get('q','').lower().strip()
    if not q: return jsonify([])
    tmpls = all_templates()
    users = load('users', {})
    results = []
    for t in list(tmpls.values())[:30]:
        name = t.get('title',t.get('name',''))
        uname = users.get(t.get('uploader_id',''),{}).get('username','')
        if q in name.lower() or q in uname.lower():
            results.append({'type':'template','id':t['id'],'name':name,'thumbnail':t.get('thumbnail',''),'uploader':uname})
    for u in list(users.values())[:20]:
        if q in u['username'].lower():
            results.append({'type':'user','username':u['username'],'avatar':u.get('avatar',''),'role':u.get('role','')})
    return jsonify(results[:12])

if __name__ == '__main__':
    app.run(debug=True, port=5000)

# ══════════════════════════════════════════════════════
#  POSTS API
# ══════════════════════════════════════════════════════

@app.route('/api/post/create', methods=['POST'])
@login_required
def api_create_post():
    user = current_user()
    d = request.get_json()
    template_id = d.get('template_id','').strip()
    caption = d.get('caption','').strip()[:500]
    if not template_id:
        return jsonify({'error':'template_id required'}), 400
    tmpl = get_template(template_id)
    if not tmpl:
        return jsonify({'error':'Template not found'}), 404
    posts = load('posts', {})
    pid = str(uuid.uuid4())
    posts[pid] = {
        'id': pid,
        'user_id': user['id'],
        'username': user['username'],
        'template_id': template_id,
        'caption': caption,
        'created_at': now_full(),
        'thumbnail': tmpl.get('thumbnail',''),
        'template_title': tmpl.get('title', tmpl.get('name','')),
        'template_bg': tmpl.get('bg',''),
    }
    save('posts', posts)
    return jsonify({'success': True, 'post_id': pid})

@app.route('/api/post/like/<pid>', methods=['POST'])
@login_required
def api_like_post(pid):
    user = current_user()
    post_likes = load('post_likes', {})
    likers = post_likes.get(pid, [])
    if user['id'] in likers:
        likers.remove(user['id'])
        action = 'unliked'
    else:
        likers.append(user['id'])
        action = 'liked'
    post_likes[pid] = likers
    save('post_likes', post_likes)
    return jsonify({'action': action, 'count': len(likers)})

@app.route('/api/post/comment/<pid>', methods=['POST'])
@login_required
def api_comment_post(pid):
    user = current_user()
    d = request.get_json()
    text = d.get('text','').strip()[:300]
    if not text:
        return jsonify({'error':'Empty comment'}), 400
    post_comments = load('post_comments', {})
    comments = post_comments.get(pid, [])
    cid = str(uuid.uuid4())
    c = {'id': cid, 'user_id': user['id'], 'username': user['username'],
         'avatar': user.get('avatar',''), 'text': text, 'created_at': now_full()}
    comments.append(c)
    post_comments[pid] = comments
    save('post_comments', post_comments)
    return jsonify({'success': True, 'comment': c})

@app.route('/api/post/comment/<pid>/<cid>', methods=['DELETE'])
@login_required
def api_delete_post_comment(pid, cid):
    user = current_user()
    post_comments = load('post_comments', {})
    comments = post_comments.get(pid, [])
    target = next((c for c in comments if c['id'] == cid), None)
    if not target:
        return jsonify({'error':'Not found'}), 404
    if target['user_id'] != user['id'] and user.get('role') != 'admin':
        return jsonify({'error':'Forbidden'}), 403
    post_comments[pid] = [c for c in comments if c['id'] != cid]
    save('post_comments', post_comments)
    return jsonify({'success': True})

@app.route('/api/post/save/<pid>', methods=['POST'])
@login_required
def api_save_post(pid):
    user = current_user()
    post_saves = load('post_saves', {})
    saved = post_saves.get(user['id'], [])
    if pid in saved:
        saved.remove(pid)
        action = 'unsaved'
    else:
        saved.append(pid)
        action = 'saved'
    post_saves[user['id']] = saved
    save('post_saves', post_saves)
    return jsonify({'action': action})

@app.route('/api/post/delete/<pid>', methods=['DELETE'])
@login_required
def api_delete_post(pid):
    user = current_user()
    posts = load('posts', {})
    post = posts.get(pid)
    if not post:
        return jsonify({'error':'Not found'}), 404
    if post['user_id'] != user['id'] and user.get('role') != 'admin':
        return jsonify({'error':'Forbidden'}), 403
    del posts[pid]
    save('posts', posts)
    return jsonify({'success': True})
