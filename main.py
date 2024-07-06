from fastapi import Depends, FastAPI
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session
from sqlalchemy import Boolean, Column, ForeignKey, create_engine, Integer, String
from pydantic import BaseModel, ConfigDict

SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"

app = FastAPI()

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    is_active = Column(Boolean, default=True)

    items = relationship("Item", back_populates="owner")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    title = Column(String, index=True)
    description = Column(String, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="items")


Base.metadata.create_all(bind=engine)


class ItemBase(BaseModel):
    title: str
    description: str | None = None

    class Meta:
        orm_model = Item


class ItemCreate(ItemBase):
    pass


class ItemRead(ItemBase):
    id: int
    owner_id: int
    model_config = ConfigDict(from_attributes=True)


class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    password: str
    items: list[ItemCreate] = []


class UserRead(UserBase):
    id: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


def is_pydantic(obj: object):
    """Checks whether an object is pydantic."""
    return type(obj).__class__.__name__ == "ModelMetaclass"


async def parse_pydantic_schema(schema):
    """
        Iterates through pydantic schema and parses nested schemas
        to a dictionary containing SQLAlchemy models.
        Only works if nested schemas have specified the Meta.orm_model.
    """
    parsed_schema = dict(schema)
    for key, value in parsed_schema.items():
        if isinstance(value, list) and len(value):
            if is_pydantic(value[0]):
                parsed_schema[key] = [schema.Meta.orm_model(**schema.model_dump()) for schema in value]
            elif is_pydantic(value):
                parsed_schema[key] = value.Meta.orm_model(**value.model_dump())

    return parsed_schema


@app.post("/users")
async def root(user: UserCreate, db: Session = Depends(get_db)):
    obj_create_data = await parse_pydantic_schema(user)
    db_user = User(**obj_create_data)

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
