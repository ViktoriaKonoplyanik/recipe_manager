from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
import os
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from werkzeug.utils import secure_filename



app = Flask(__name__, template_folder='templates')
secret_key = os.urandom(24)
app.config['SECRET_KEY'] = secret_key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
migrate = Migrate(app, db)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    recipes = db.relationship('Recipes', backref='author', lazy=True)



class Recipes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=True)
    prep_time = db.Column(db.String(20), nullable=False)
    ingredients = db.Column(db.Text, nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipe_comments = db.relationship('Comment', backref='recipe', cascade='all, delete-orphan')


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id'), nullable=False)

    user = db.relationship('User', backref=db.backref('comments', lazy=True))
    related_recipe = db.relationship('Recipes', backref=db.backref('comments', lazy=True))

    def __repr__(self):
        return '<Recipes %r>' % self.id



@app.route('/', methods=['GET', 'POST'])
def index():
    categories = ['Завтрак', 'Обед', 'Ужин', 'Десерт', 'Напитки']

    if request.method == 'POST':
        if 'user_id' not in session:
            flash('Необходимо зарегистрироваться, чтобы добавить рецепт.', 'danger')
            return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        category = request.form['category']
        description = request.form['description']
        prep_time = request.form['prep_time']
        ingredients = request.form['ingredients']
        instructions = request.form['instructions']
        image = request.files['image']


        image.save('static/images/' + image.filename)
        new_recipe = Recipes(title=title, category=category, description=description,
                             prep_time=prep_time, ingredients=ingredients,
                             instructions=instructions, image=image.filename, user_id=session['user_id'])
        db.session.add(new_recipe)
        db.session.commit()
        flash('Рецепт добавлен успешно!', 'success')
        return redirect(url_for('index'))

    return render_template("index.html", categories=categories)


@app.route('/posts')
def posts():
    categories = db.session.query(Recipes.category).distinct().all()
    category_filter = request.args.get('category')
    if category_filter:
        recipes = Recipes.query.filter_by(category=category_filter).all()
    else:
        recipes = Recipes.query.all()
    return render_template('posts.html', recipes=recipes, categories=categories)



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = bcrypt.generate_password_hash(request.form['password'])
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Имя пользователя уже занято. Пожалуйста, выберите другое.', 'danger')
            return render_template('register.html')


        user = User(username=username, password=password)
        db.session.add(user)
        try:
            db.session.commit()
            flash('Аккаунт успешно создан!', 'success')
            return redirect(url_for('login'))
        except IntegrityError:
            db.session.rollback()
            flash('Произошла ошибка при создании аккаунта. Попробуйте снова.', 'danger')
            return render_template('register.html')
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username

            return redirect(url_for('index'))
        else:
            flash('Ошибка входа. Проверьте свои учетные данные.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('login'))


@app.route('/delete_recipe/<int:id>', methods=['POST'])
def delete_recipe(id):
    recipe = Recipes.query.get_or_404(id)
    if recipe.user_id != session.get('user_id'):
        flash('У вас нет прав на удаление этого рецепта.', 'danger')
        return redirect(url_for('posts'))
    db.session.delete(recipe)
    db.session.commit()
    flash('Рецепт удален.', 'success')
    return redirect(url_for('posts'))
@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query')
    if query is not None:
        query = query.lower()

    if query:
        # Выполните поиск в базе данных по названию, ингредиентам или категориям
        recipes = Recipes.query.filter(
            (Recipes.title.ilike(f'%{query}%')) |
            (Recipes.ingredients.ilike(f'%{query}%')) |
            (Recipes.category.ilike(f'%{query}%'))
        ).all()
    else:
        # Если запрос пуст, верните пустой список рецептов
        recipes = []

    return render_template('search_results.html', recipes=recipes)


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
@app.route('/edit_recipe/<int:id>', methods=['GET', 'POST'])
def edit_recipe(id):
    if 'user_id' not in session:
        flash('Необходимо зарегистрироваться, чтобы редактировать рецепт.', 'danger')
        return redirect(url_for('login'))

    recipe = Recipes.query.get_or_404(id)
    if recipe.author.id != session['user_id']:
        flash('Вы можете редактировать только свои собственные рецепты.', 'danger')
        return redirect(url_for('posts'))

    if request.method == 'POST':
        recipe.title = request.form['title']
        recipe.category = request.form['category']
        recipe.description = request.form['description']
        recipe.prep_time = request.form['prep_time']
        recipe.ingredients = request.form['ingredients']
        recipe.instructions = request.form['instructions']

        if 'image' in request.files and request.files['image'].filename != '':
            image = request.files['image']
            if image and allowed_file(image.filename):
                filename = secure_filename(image.filename)
                image_path = os.path.join('static/images', filename)
                image.save(image_path)
                recipe.image = filename  # Update image path in the database

        db.session.commit()
        flash('Рецепт успешно обновлен!', 'success')
        return redirect(url_for('posts'))

    categories = ['Завтрак', 'Обед', 'Ужин', 'Десерт', 'Напитки']
    return render_template('edit_recipe.html', recipe=recipe, categories=categories)


@app.route('/recipe/<int:recipe_id>/comment', methods=['POST'])
def add_comment(recipe_id):
    if 'user_id' not in session:
        flash('Необходимо зарегистрироваться, чтобы оставлять комментарии.', 'danger')
        return redirect(url_for('login'))

    content = request.form['content']
    if content:
        new_comment = Comment(content=content, user_id=session['user_id'], recipe_id=recipe_id)
        db.session.add(new_comment)
        db.session.commit()
        flash('Комментарий добавлен!', 'success')
    else:
        flash('Комментарий не может быть пустым.', 'danger')

    return redirect(url_for('posts'))


@app.route('/delete_comment/<int:id>', methods=['POST'])
def delete_comment(id):
    comment = Comment.query.get_or_404(id)
    if comment.user_id == session.get('user_id'):
        db.session.delete(comment)
        db.session.commit()
        flash('Комментарий удален.', 'success')
    else:
        flash('У вас нет прав на удаление этого комментария.', 'danger')
    return redirect(url_for('posts'))



if __name__ == '__main__':
    app.run(port=50001, debug=True)