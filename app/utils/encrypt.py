import bcrypt  # 导入 bcrypt 库，用于密码的哈希与校验


def hash_password(password: str) -> str:  # 定义哈希函数：明文密码 -> bcrypt 哈希
    """明文密码 -> bcrypt 哈希（含盐）"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")  # 密码转字节 -> 加盐哈希 -> 转回字符串返回


def verify_password(password: str, hashed: str) -> bool:  # 定义校验函数：明文密码与已存哈希比对
    """校验明文密码是否匹配已存哈希"""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))  # 明文与哈希都转字节后比对，返回布尔结果