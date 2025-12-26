import unittest
from app import app, db

class TestFlaskIntegrity(unittest.TestCase):
    def setUp(self):
        # Configuración para pruebas
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        with app.app_context():
            db.create_all()

    def test_acceso_login(self):
        """Verifica que la app arranca y muestra el login."""
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)

    def test_redireccion_sin_login(self):
        """Verifica que si intentas ir al index sin loguearte, te redirige."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)