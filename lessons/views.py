import pandas as pd
from django.shortcuts import render, redirect
from fsrs import FSRS, Card, Rating, State
from datetime import datetime, timezone, timedelta
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
import random



f = FSRS()


gc = gspread.service_account(filename='service_account.json')


sh = gc.open("ArabicCampVocabulary")
worksheet = sh.get_worksheet(0) # 0 is the first tab


df = get_as_dataframe(worksheet)
# Define all columns required by the FSRS algorithm
required_columns = {
    'space1' :'',
    'space2' : '',
    'space3' : '', 
    'space4' :'',
    'space5' : '',
    'space6' : '', 
    'due': datetime.now(timezone.utc),
    'stability': 0.0,
    'difficulty': 0.0,
    'reps': 0,
    'lapses': 0,
    'state': State.New.value,
    'last_review': datetime.now(timezone.utc)
}
df.loc[df['due'].isna() , ['due', 'stability','difficulty','reps','lapses','state','last_review']] = [datetime.now(timezone.utc),0.0,0.0,0,0,State.New.value,datetime.now(timezone.utc)]
for col, default_val in required_columns.items():
    if col not in df.columns:
        print(f"Adding missing column: {col}")
        df[col] = default_val


df['due'] = pd.to_datetime(df['due'], utc=True)
df['last_review'] = pd.to_datetime(df['last_review'], utc=True)

new_mask = (df['reps'].isna()) | (df['reps'] == 0)
df.loc[new_mask, 'state'] = State.New.value


now = datetime.now(timezone.utc)

# Find existing words that are actually due
due_reviews = df[(df['due'] <= now) & (df['reps'] > 0)]

# . Pick 10 brand new words to introduce this session
unseen_words = df[df['reps'] == 0]
num_to_sample = min(10, len(unseen_words))
new_indices = unseen_words.sample(num_to_sample).index

# Activate those 10 new words by setting their due date to NOW
df.loc[new_indices, 'due'] = now

#if this doesn't work you can always use sample or seed, bcs here i think it's getting the first 20 words order wise rather than the 20 most overdue words
due_queue = df[df['due'] <= now].sort_values(by='due').head(20)
counter = 0 
'''
print(f"--- Session Starting! ---")
print(f"Reviews due: {len(due_reviews)} | New words today: {len(new_indices)}")
print("-" * 25)'''

#since variables look like they are stored here in a dict called context within the quiz_view function, you might as well just launch ur program as usual, and then store everything here
def quiz_view(request):
    show_feedback = False 
    if request.method == "POST":
        user_input = request.POST.get('user_answer') # Grabs what they typed
        user_choice = request.POST.get('user_choice') 
        # Here is where you put your comparison logic
        # For example: 
        # if user_input == correct_answer: 
        #     update_fsrs_metrics()
        if user_input == 'Y':
            show_feedback = True
        print(f"User guessed: {user_input} ") 
        print(f"User was: {user_choice} ") 
        print(f"Feedback: {show_feedback} ") 
        # After processing, we usually redirect to the same page to get a NEW word
        #return redirect('quiz_url_name')
    # Check if the queue is empty first to avoid errors
    if not due_queue.empty:
        # .iloc[0] gets the first row, ['Arabic'] gets the text from that column
        word_to_showA = due_queue.iloc[0]['Arabic']
        word_to_showF = due_queue.iloc[0]['Franco ']
    else:
        word_to_show = "No more words!" 
    # Create the dictionary
    context = {
        'display_wordA': word_to_showA,
        'display_wordF': word_to_showF,
        'show_feedback' : show_feedback,
    }
    
    # Render with the correct filename and the dictionary
    return render(request, 'lessons/quiz.html', context)
