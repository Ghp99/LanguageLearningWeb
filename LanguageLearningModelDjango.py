import pandas as pd
from django.shortcuts import render, redirect
from fsrs import FSRS, Card, Rating, State
from datetime import datetime, timezone
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe

# Global FSRS init
f = FSRS()

def get_sheet():
    gc = gspread.service_account(filename='service_account.json')
    sh = gc.open("ArabicCampVocabulary")
    return sh.get_worksheet(0)

def quiz_view(request):
    # --- STEP 1: INITIALIZE SESSION ---
    if 'quiz_data' not in request.session:
        worksheet = get_sheet()
        df = get_as_dataframe(worksheet)
        
        # ... Insert your column cleanup logic here ...
        
        now = datetime.now(timezone.utc)
        # Get your 20 words
        due_queue = df[df['due'] <= now.isoformat()].sort_values(by='due').head(20)
        
        # Store essential data in session (Sessions can't hold DataFrames, only lists/dicts)
        request.session['quiz_data'] = due_queue.to_dict('records')
        request.session['current_index'] = 0
        request.session['score'] = 0

    # --- STEP 2: HANDLE USER ANSWER ---
    quiz_data = request.session['quiz_data']
    idx = request.session['current_index']

    if idx >= len(quiz_data):
        return render(request, 'lessons/complete.html', {'score': request.session['score']})

    current_card_data = quiz_data[idx]

    if request.method == "POST":
        user_rating = request.POST.get('rating') # 'good' or 'again'
        is_correct = (user_rating == 'good')
        
        if is_correct:
            request.session['score'] += 1

        # FSRS LOGIC
        card = Card(
            due=datetime.fromisoformat(current_card_data['due']),
            stability=current_card_data['stability'],
            difficulty=current_card_data['difficulty'],
            reps=current_card_data['reps'],
            lapses=current_card_data['lapses'],
            state=State(current_card_data['state'])
        )
        
        rating = Rating.Good if is_correct else Rating.Again
        scheduling_info = f.repeat(card, datetime.now(timezone.utc))
        new_card = scheduling_info[rating].card

        # --- STEP 3: UPDATE GOOGLE SHEETS ---
        # Note: In Django, we update the specific row immediately
        # You'll need the index from the original DF to use df.at[] 
        # or use a unique ID to find the row in the sheet
        update_google_sheet_row(current_card_data['English '], new_card)

        request.session['current_index'] += 1
        request.session.modified = True
        return redirect('quiz_view')

    return render(request, 'lessons/quiz.html', {'card': current_card_data})