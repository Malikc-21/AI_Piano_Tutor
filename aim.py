import gradio as gr
from music21 import *

# Function to parse music files and compare them
def parse_and_compare(score1_file, score2_file):
    try:
        # Parse the input music scores using the file paths
        parsedWork1 = converter.parse(score1_file.name)
        parsedWork2 = converter.parse(score2_file.name)
        
        recurse_work1 = parsedWork1.recurse()
        recurse_work2 = parsedWork2.recurse()

        # Create empty score objects
        new_score1 = stream.Score()
        new_score2 = stream.Score()

        # Append notes and rests to the score objects
        for element in recurse_work1.notesAndRests:
            new_score1.append(element)

        for element in recurse_work2.notesAndRests:
            new_score2.append(element)

        # Lists to track skipped and extra notes along with their measures
        skipped_notes = []  # Notes removed from score1
        extra_notes = []    # Notes removed from score2
        correct_notes = 0   # Count of correct notes
        total_notes = 0     # Count of total notes

        # Mistakes counter to track types of mistakes
        mistakes_counter = {
            'note_mismatch': 0,  # Incorrect note played
            'rhythm_mismatch': 0,  # Incorrect rhythm
            'chord_mismatch': 0,  # Incorrect chord
            'missed_note': 0,  # Missed note (rest instead)
            'extra_note': 0,  # Extra note (played during rest)
        }

        # Function to handle note value discrepancies
        def handle_note_value_discrepancies(score1, score2, index):
            total_deleted_length = 0
            while index < len(score1) and index < len(score2):
                note1 = score1[index]
                note2 = score2[index]

                if note1.quarterLength != note2.quarterLength:
                    if note1.quarterLength > note2.quarterLength:
                        # Remove notes from score2 (extra notes)
                        while total_deleted_length < (note1.quarterLength - note2.quarterLength):
                            if index < len(score2):
                                # Capture the correct note and its measure for removal
                                measure = note2.getContextByClass(stream.Measure)
                                extra_notes.append((note2, measure))  # Track extra notes with measure
                                score2.pop(index)  # Remove the note from score2
                                total_deleted_length += note2.quarterLength
                            else:
                                break
                    else:
                        # Remove notes from score1 (skipped notes)
                        while total_deleted_length < (note2.quarterLength - note1.quarterLength):
                            if index < len(score1):
                                # Capture the correct note and its measure for removal
                                measure = note1.getContextByClass(stream.Measure)
                                skipped_notes.append((note1, measure))  # Track skipped notes with measure
                                score1.pop(index)  # Remove the note from score1
                                total_deleted_length += note1.quarterLength
                            else:
                                break
                else:
                    # No discrepancy, break the loop
                    break

                return index  # This should return the index when modifications happen.

            return index + 1  # We increment index only when no changes happen, and the next note needs to be processed.

        # Dictionary to store feedback by measure number
        feedback_group = {}

        i = 0
        while i < min(len(new_score1), len(new_score2)):
            new_i = handle_note_value_discrepancies(new_score1, new_score2, i)
            if new_i is not None:
                i = new_i
                if i < len(new_score1) and i < len(new_score2):
                    note1 = new_score1[i]
                    note2 = new_score2[i]
                    measure = note1.getContextByClass(stream.Measure)

                    # Initialize measure feedback if it doesn't exist
                    if measure is not None:
                        if measure.measureNumber not in feedback_group:
                            feedback_group[measure.measureNumber] = []

            i += 1

        # Comparing note counts
        if len(new_score1) != len(new_score2):
            feedback_group['Note Count'] = [f"Different amount of notes: {len(new_score1)} vs {len(new_score2)}"]
        else:
            feedback_group['Note Count'] = [f"Note Count: {len(new_score1)} vs {len(new_score2)}"]


        # Iterate through the scores and provide feedback on musical accuracy
        for i in range(min(len(new_score1), len(new_score2))):
            note1 = new_score1[i]
            note2 = new_score2[i]
            measure = note1.getContextByClass(stream.Measure)

            if measure is not None:
                if measure.measureNumber not in feedback_group:
                    feedback_group[measure.measureNumber] = []

            # Check various conditions and append feedback to the correct measure
            if note1.isRest and note2.isRest:
                correct_notes += 1
                total_notes += 1
                continue  # Skip comparison if both are rests
            elif note1.isRest and not note2.isRest:
                feedback_group[measure.measureNumber].append(f"⚠️ You played a note during a rest: rest vs What you played {note2.nameWithOctave}")
                mistakes_counter['extra_note'] += 1  # Track extra note mistake
                total_notes += 1
            elif note2.isRest and not note1.isRest:
                feedback_group[measure.measureNumber].append(f"❌ You missed a note and added a rest: What you played {note1.nameWithOctave} vs rest")
                mistakes_counter['missed_note'] += 1  # Track missed note mistake
                total_notes += 1
            else:
                # Compare chords
                if note1.isChord and note2.isChord:
                    played_chord1 = [p.name for p in note1.pitches]
                    played_chord2 = [p.name for p in note2.pitches]

                    if set(played_chord1) != set(played_chord2):
                        feedback_group[measure.measureNumber].append(f"⚠️ Wrong chord played: You played ({', '.join(played_chord1)}), the correct chord is ({', '.join(played_chord2)})")
                        mistakes_counter['chord_mismatch'] += 1  # Track chord mismatch
                    else:
                        correct_notes += 1
                        total_notes += 1
                elif note1.isChord and not note2.isChord:
                    # If note1 is a chord and note2 is not, still need to define played_chord2
                    played_chord2 = [p.name for p in note1.pitches]  # Use note1 for the correct chord
                    feedback_group[measure.measureNumber].append(f"❌ You did not play the correct chord. The correct chord is ({', '.join(played_chord2)})")
                    mistakes_counter['chord_mismatch'] += 1  # Track chord mismatch
                    total_notes += 1
                elif not note1.isChord and note2.isChord:
                    feedback_group[measure.measureNumber].append(f"⚠️ A note was incorrectly played as a chord")    
                    mistakes_counter['chord_mismatch'] += 1  # Track chord mismatch
                # Check for both note and rhythm mismatches
                elif note1.nameWithOctave != note2.nameWithOctave and note1.quarterLength != note2.quarterLength:
                    correct_duration_name = note1.duration.type
                    played_duration_name = note2.duration.type
                    feedback_group[measure.measureNumber].append(f"❌ Wrong note and wrong rhythm: Correct note: {note1.nameWithOctave} ({correct_duration_name}) vs What you played: {note2.nameWithOctave} ({played_duration_name})")
                    mistakes_counter['note_mismatch'] += 1  # Track note mismatch
                    total_notes += 1
                # Check for rhythm mismatches
                elif note1.quarterLength != note2.quarterLength and note1.nameWithOctave == note2.nameWithOctave:
                    correct_duration_name = note1.duration.type
                    played_duration_name = note2.duration.type
                    feedback_group[measure.measureNumber].append(f"⚠️ Wrong rhythm: Correct note value: {correct_duration_name} vs What you played: {played_duration_name}")
                    mistakes_counter['rhythm_mismatch'] += 1  # Track rhythm mismatch
                    total_notes += 1
                # Check for note mismatches
                elif note1.quarterLength == note2.quarterLength and note1.nameWithOctave != note2.nameWithOctave:
                    feedback_group[measure.measureNumber].append(f"❌ Incorrect note played: Correct note: {note1.nameWithOctave} vs What you played: {note2.nameWithOctave}")
                    mistakes_counter['note_mismatch'] += 1  # Track note mismatch
                    total_notes += 1
                else:
                    correct_notes += 1
                    total_notes += 1

        # Calculate accuracy percentage
        accuracy_percentage = (correct_notes / total_notes) * 100 if total_notes > 0 else 100

        # Format feedback output, showing only measures with errors
        feedback_output = f"Your accuracy: {accuracy_percentage:.2f}%\n\n"
        for measure, feedback in feedback_group.items():
            if measure != 'Note Count' and feedback:  # Only show measures that have feedback
                feedback_output += f"Measure {measure}:\n" + "\n".join(feedback) + "\n\n"

        # Provide the feedback along with skipped and extra notes
        skipped_notes_text = f"Notes you may have skipped: {len(skipped_notes)}\n"
        skipped_notes_text += "\n".join([f"  - {note[0].nameWithOctave} in measure {note[1].measureNumber}" for note in skipped_notes]) + "\n"

        extra_notes_text = f"Extra notes you may have played: {len(extra_notes)}\n"
        extra_notes_text += "\n".join([f"  - {note[0].nameWithOctave} in measure {note[1].measureNumber}" for note in extra_notes]) + "\n"

        # Recommendation for improvement based on mistake types
        recommendations = []
        if mistakes_counter['note_mismatch'] > mistakes_counter['rhythm_mismatch']:
            recommendations.append("Focus on playing the correct notes first, then pay attention to rhythm.")
        elif mistakes_counter['rhythm_mismatch'] > mistakes_counter['note_mismatch']:
            recommendations.append("Your rhythm needs improvement. Focus on getting the correct timing first.")
        if mistakes_counter['chord_mismatch'] > 0:
            recommendations.append("Review your chord shapes and their inversions.")
        if mistakes_counter['missed_note'] > 0:
            recommendations.append("Make sure you don't miss any notes, especially if it's a rest you need to replace.")
        if mistakes_counter['extra_note'] > 0:
            recommendations.append("Avoid playing extra notes during rests.")

        recommendations_text = "\n".join(recommendations) if recommendations else "You're doing well! Keep practicing."

        return feedback_output, skipped_notes_text, extra_notes_text, recommendations_text

    except Exception as e:
        return f"Error occurred: {str(e)}", "", "", ""

# Gradio interface function
def get_feedback(score1_file, score2_file):
    return parse_and_compare(score1_file, score2_file)

# Set up Gradio UI
with gr.Blocks() as demo:
    gr.Markdown("### Music Feedback")
    with gr.Row():
        score1_file = gr.File(label="Upload Student's Score")
        score2_file = gr.File(label="Upload Reference Score")
        submit_button = gr.Button("Submit")
    output_text = gr.Textbox(label="Feedback", lines=20)
    recommendations_output = gr.Textbox(label="Recommendations", lines=5)
    skipped_notes_output = gr.Textbox(label="Skipped Notes", lines=5)
    extra_notes_output = gr.Textbox(label="Extra Notes", lines=5)

    
    submit_button.click(get_feedback, inputs=[score1_file, score2_file], outputs=[output_text, skipped_notes_output, extra_notes_output, recommendations_output])

demo.launch()




