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

#ok but what if i want some words to get asked twice in the same session? asking twice would be a good idea?
#i can always put the words I got wrong per session in a temporary ds and randomy ask 3 of them
'''

#so basically what I'm doing here is like i am executing a single word, if the user goes through the check i save the info, then i refresh the page, which executes a single word.... and so on and so forth up until there are no more words
def quiz_view(request):
    # 1. STOP: Don't use a loop. Just get the TOP word in the queue.
    if due_queue.empty:
        return render(request, 'lessons/quiz.html', {'display_wordA': "Finished!"})
    #let's fix the counter later
    #counter = 0
    word_index = due_queue.index[0] # Get the ID of the first word
    word_row = df.loc[word_index]
    English = word_row['English ']
    Franco = word_row['Franco ']
    Arabic = word_row['Arabic']
    lang_from = random.choice(['English ', 'Franco ', 'Arabic'])
    vocab = word_row[lang_from]
    show_feedback = False
    is_correct = False
    user_input = ""
    if lang_from in ['Franco ', 'Arabic']:
        correct_answer = English
    else:
        #here it just choses which language to prompt the user within arabic and franco
        #target_lang = random.choice(['Franco ', 'Arabic'])
        #prompt = f"Translate '{vocab}' to {target_lang}: "
        #just set it to arabic for a sec
        correct_answer = word_row[Arabic]
    # 2. Logic to handle the user's answer (The POST)
    print(show_feedback)
    if request.method == "POST":
        user_answer = request.POST.get('user_answer')
        user_choice = request.POST.get('user_choice') # This comes from the ✅/❌ buttons
        print(f'user answer is: {user_answer}')
        # PHASE A: User just typed their answer
        if user_answer and not user_choice:
            show_feedback = True
            user_input = user_answer
            # We don't save yet! We just stop here and show the emojis.
            print(f'user choice is {user_choice}')
            print(f'is_correct is {is_correct}')
            
        # PHASE B: User clicked ✅ or ❌
        elif user_choice:
            is_correct = (user_choice == 'correct')
            print(f'user choice is {user_choice}')
            print(f'is_correct is {is_correct}')
            #if is_correct:
                #counter += 1
        
        #move this to the html in a little part of the screen
        #print(f"\n[Reps: {int(word_row['reps'])} | Difficulty: {word_row['difficulty']:.1f}]")
    
            card = Card(
            due=word_row['due'].to_pydatetime(),
            stability=word_row['stability'],
            difficulty=word_row['difficulty'],
            reps=int(word_row['reps']),
            lapses=int(word_row['lapses']),
            state=State(word_row['state'])
            )
    # The FSRS library needs this attribute specifically to calculate elapsed time
            if pd.notna(word_row['last_review']):
                card.last_review = word_row['last_review'].to_pydatetime()

            rating = Rating.Good if is_correct else Rating.Again
    
    # Use the FSRS model to calculate the new brain metrics
            scheduling_info = f.repeat(card, now)
            new_card = scheduling_info[rating].card

            df.at[word_index, 'due'] = new_card.due
            df.at[word_index, 'stability'] = new_card.stability
            df.at[word_index, 'difficulty'] = new_card.difficulty
            df.at[word_index, 'reps'] = new_card.reps
            df.at[word_index, 'lapses'] = new_card.lapses
            df.at[word_index, 'state'] = new_card.state.value
            df.at[word_index, 'last_review'] = now 


            temp_df = df.copy()
    
            for col in ['due', 'last_review']:
                if temp_df[col].dt.tz is not None:
                    temp_df[col] = temp_df[col].dt.tz_localize(None)
            set_with_dataframe(worksheet, temp_df, include_index=False)
            return redirect('quiz_page')         
    context = {
        'display_word': vocab,
        'correct_answer': correct_answer,
        'show_feedback': show_feedback,
        'user_input': user_input,
        'reps': int(word_row['reps']),
        'difficulty': round(float(word_row['difficulty']), 1),
        #'counter' : counter
    }
    return render(request, 'lessons/quiz.html', context)'''
        
'''
    print("Session complete! All progress saved.")
    print(f"You got {counter} words right")'''
        
def quiz_view(request):
    # 1. RE-CALCULATE THE QUEUE EVERY TIME (Inside the view)
    now = datetime.now(timezone.utc)
    
    # This ensures that if you just saved a word's 'due' date to next week, 
    # it immediately disappears from this filtered list.
    current_due_queue = df[df['due'] <= now].sort_values(by='due').head(20)

    if current_due_queue.empty:
        return render(request, 'lessons/quiz.html', {'display_word': "Finished!"})
    
    # 2. Get the top word from our NEWLY calculated queue
    word_index = current_due_queue.index[0] 
    word_row = df.loc[word_index]
    
    # ... (Your language choice logic) ...
    English = word_row['English ']
    Arabic = word_row['Arabic']
    #lang_from = random.choice(['English ', 'Franco ', 'Arabic'])
    session_key = f"lang_choice_{word_index}"
    
    if session_key in request.session:
        lang_from = request.session[session_key]
    else:
        lang_from = random.choice(['English ', 'Franco ', 'Arabic'])
        request.session[session_key] = lang_from
    vocab = word_row[lang_from]
    sheet_row_number = word_index + 2
    correct_answer = English if lang_from in ['Franco ', 'Arabic'] else Arabic
    show_feedback = False
    is_correct = False
    user_input = ""
    print(lang_from)
    if request.method == "POST":
        user_answer = request.POST.get('user_answer')
        user_choice = request.POST.get('user_choice')
        button_pressed = request.POST.get('action')
        
        if user_answer or button_pressed and not user_choice:
            show_feedback = True
            user_input = user_answer
            
        elif user_choice:
            is_correct = (user_choice == 'correct')
            
            # --- FSRS MATH ---
            card = Card(
                due=word_row['due'].to_pydatetime(),
                stability=word_row['stability'],
                difficulty=word_row['difficulty'],
                reps=int(word_row['reps']),
                lapses=int(word_row['lapses']),
                state=State(word_row['state'])
            )
            
            if pd.notna(word_row['last_review']):
                card.last_review = word_row['last_review'].to_pydatetime()

            rating = Rating.Good if is_correct else Rating.Again
            scheduling_info = f.repeat(card, now)
            new_card = scheduling_info[rating].card

            # --- UPDATE THE MASTER DATAFRAME ---
            
            df.at[word_index, 'due'] = new_card.due
            df.at[word_index, 'stability'] = new_card.stability
            df.at[word_index, 'difficulty'] = new_card.difficulty
            df.at[word_index, 'reps'] = new_card.reps
            df.at[word_index, 'lapses'] = new_card.lapses
            df.at[word_index, 'state'] = new_card.state.value
            df.at[word_index, 'last_review'] = now 
             
            updated_row = df.loc[word_index].copy()

            # 2. Format datetimes to strings (Google Sheets doesn't natively accept Python datetimes)
            for col in ['due', 'last_review']:
                if pd.notna(updated_row[col]):
                    dt_val = updated_row[col]
                    # Strip timezone if it exists
                    if dt_val.tzinfo is not None:
                        dt_val = dt_val.tz_localize(None)
                    # Convert to string format
                    updated_row[col] = dt_val.strftime('%Y-%m-%d %H:%M:%S')

            # 3. Convert row to list and replace NaNs with empty strings (gspread hates NaNs)
            row_values = ["" if pd.isna(val) else val for val in updated_row.tolist()]

            # 4. Update just that specific row in Google Sheets
            # Note: We wrap row_values in an outer list [row_values] because it expects a 2D array
            range_name = f"A{sheet_row_number}"
            
            try:
                # For newer versions of gspread (v6.0.0+)
                worksheet.update(values=[row_values], range_name=range_name)
            except TypeError:
                # For older versions of gspread
                worksheet.update(range_name, [row_values])

            # This triggers the function to run again, recalculating the queue!
            return redirect('quiz_page')
    context = {
        'display_word': vocab,
        'correct_answer': correct_answer,
        'show_feedback': show_feedback,
        'user_input': user_input,
        'reps': int(word_row['reps']),
        'difficulty': round(float(word_row['difficulty']), 1),
    }
    return render(request, 'lessons/quiz.html', context)
        
