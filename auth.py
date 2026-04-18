from passlib.context import CryptContext

# ÖZAS Digital Güvenlik Katmanı - Şifreleme Ayarları
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str):
    """Kullanıcı şifresini kimsenin çözemeyeceği bir koda dönüştürür."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    """Giriş yapılan şifrenin doğruluğunu kontrol eder."""
    return pwd_context.verify(plain_password, hashed_password)