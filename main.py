from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
import json
from fuzzywuzzy import fuzz
import base64
from PIL import Image
import io
import pytesseract
from sqlmodel import Field, SQLModel, Session, create_engine, select
from typing import Optional, List

# Define your data model
class QA(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    question: str
    answer: str
    links: str  # Store JSON string of links

# Create the SQLite database engine
sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url, echo=True)

# Create the database and tables
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

app = FastAPI()

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    # Uncomment to load initial data from JSON
    # load_initial_data()

# Dependency
def get_session():
    with Session(engine) as session:
        yield session

# OCR setup
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_text_from_image(base64_str):
    try:
        image_data = base64.b64decode(base64_str)
        image = Image.open(io.BytesIO(image_data))
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        return ""

class QuestionRequest(BaseModel):
    question: str
    image: Optional[str] = None

class QACreate(BaseModel):
    question: str
    answer: str
    links: List[dict]

def load_initial_data():
    with Session(engine) as session:
        with open("answers.json", "r") as f:
            answers = json.load(f)
            for item in answers:
                qa = QA(
                    question=item["question"],
                    answer=item["answer"],
                    links=json.dumps(item["links"])
                )
                session.add(qa)
        session.commit()

@app.get("/")
async def root():
    return {"message": "TDS Virtual TA API is running!"}

@app.post("/api/")
async def answer_question(req: QuestionRequest, session: Session = Depends(get_session)):
    # Handle image input
    question_text = req.question
    if req.image:
        extracted_text = extract_text_from_image(req.image)
        if extracted_text:
            question_text = extracted_text
        else:
            return {"answer": "Could not extract text from image.", "links": []}

    # Search database with fuzzy matching
    best_score = 0
    best_qa = None
    
    qas = session.exec(select(QA)).all()
    for qa in qas:
        score = fuzz.token_set_ratio(question_text.lower(), qa.question.lower())
        if score > best_score:
            best_score = score
            best_qa = qa

    if best_score > 70 and best_qa:
        return {
            "answer": best_qa.answer,
            "links": json.loads(best_qa.links)
        }
    
    return {"answer": "Sorry, I don't know the answer yet.", "links": []}

@app.post("/add_qa/")
async def add_qa(qa: QACreate, session: Session = Depends(get_session)):
    db_qa = QA(
        question=qa.question,
        answer=qa.answer,
        links=json.dumps(qa.links)
    )
    session.add(db_qa)
    session.commit()
    session.refresh(db_qa)
    return db_qa

@app.get("/all_qa/")
async def get_all_qa(session: Session = Depends(get_session)):
    qas = session.exec(select(QA)).all()
    return qas
