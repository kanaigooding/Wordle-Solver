import sys
import tkinter as tk
from pathlib import Path

if not __package__:
    # Running as a script (python src/gui/...): make the solver package importable.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solver import WordleSolver

class WordleSolverGUI(tk.Tk):
    def __init__(self, solver):
        super().__init__()
        self.configure(bg='light grey')
        self.title('Wordle Solver')
        self.geometry('400x300')

        self.solver = solver
        self.guesses = []

        self.feedback_colors = {'G': 'green', 'Y': 'yellow', 'B': 'dark grey'}

        self.entry_fields = self._initialize_entries()
        self.feedback_buttons = self._initialize_buttons()
        self._initialize_submit_button()
        self.result_label, self.possible_guesses_label = self._initialize_labels()

    def _initialize_entries(self):
        """Initialize entry fields for user input."""
        entries = []
        for i in range(5):
            entry = self._create_entry_field(i)
            entries.append(entry)
        return entries

    def _create_entry_field(self, index):
        """Create an individual entry field for a letter."""
        entry_position = 50 + index * 70
        validate_command = self.register(self.limit_input_to_single_character)
        entry = tk.Entry(self, width=2, validate='key', validatecommand=(validate_command, '%P'))
        entry.config(font=('Helvetica', 24), justify='center', bg='dark grey')
        entry.bind('<Key>', lambda e, i=index: self.focus_on_next_entry(i))
        entry.place(x=entry_position, y=100)
        return entry

    def _initialize_buttons(self):
        """Initialize feedback buttons for each letter."""
        buttons = []
        for i in range(5):
            button = self._create_feedback_button(i)
            buttons.append(button)
        return buttons

    def _create_feedback_button(self, index):
        """Create a feedback button for a letter."""
        button_position = 50 + index * 70
        button = tk.Button(self, text='B', width=2, height=1, bg='dark grey')
        button.config(font=('Helvetica', 24))
        button.place(x=button_position, y=150)
        button.bind('<Button-1>', self.cycle_feedback_color)
        return button

    def _initialize_submit_button(self):
        """Initialize the submit button."""
        submit_button = tk.Button(self, text='Submit', command=self.submit_guess)
        submit_button.place(x=150, y=220)

    def _initialize_labels(self):
        """Initialize labels for results and possible guesses."""
        result_label = tk.Label(self, text='', bg='light grey')
        result_label.place(x=100, y=280)

        possible_guesses_label = tk.Label(self, text='', bg='light grey')
        possible_guesses_label.place(x=100, y=250)

        return result_label, possible_guesses_label

    def limit_input_to_single_character(self, input):
        """Limit input to a single character."""
        return len(input) <= 1

    def focus_on_next_entry(self, index):
        """Focus on the next entry field."""
        if index < 4:
            self.entry_fields[index + 1].focus()

    def submit_guess(self):
        """Submit the current guess and get the optimal next guess."""
        guessed_word = ''.join(entry.get().lower() for entry in self.entry_fields)
        feedback = [button['text'] for button in self.feedback_buttons]
        self.solver.adjust_guess(guessed_word, feedback)
        optimal_guess = self.solver.get_optimal_guess()
        self.result_label['text'] = f'Optimal Guess: {optimal_guess}'
        self.guesses.append((guessed_word, feedback))

        for entry, button in zip(self.entry_fields, self.feedback_buttons):
            entry.delete(0, tk.END)
            button['text'] = 'B'
            button['bg'] = 'dark grey'

        self.possible_guesses_label['text'] = f'Possible guesses remaining: {len(self.solver.possible_words)}'

    def cycle_feedback_color(self, event):
        """Cycle through feedback colors for a button."""
        current_feedback = event.widget['text']
        feedback_values = list(self.feedback_colors.keys())
        new_feedback = feedback_values[(feedback_values.index(current_feedback) + 1) % len(feedback_values)]
        event.widget['text'] = new_feedback
        event.widget['bg'] = self.feedback_colors[new_feedback]

def main():
    solver_gui = WordleSolverGUI(WordleSolver.from_default_files())
    solver_gui.mainloop()


if __name__ == "__main__":
    main()