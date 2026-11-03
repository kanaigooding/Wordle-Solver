import sys
import tkinter as tk
from pathlib import Path

if not __package__:
    # Running as a script (python src/gui/...): make the solver package importable.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solver import WordleSolver

class QuordleGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.configure(bg='light grey')
        self.title('Quordle Solver')
        self.geometry('900x700')

        self.solvers = [WordleSolver.from_default_files() for _ in range(4)]

        self.guesses = [[] for _ in range(4)]
        self.feedback_colors = {'G': 'green', 'Y': 'yellow', 'B': 'dark grey'}

        self.entries_vars = [tk.StringVar() for _ in range(5)]
        self.entries = self._initialize_entries()
        self.feedback_buttons = self._initialize_feedback_buttons()
        self._initialize_submit_button()
        self.result_labels, self.possible_guesses_labels = self._initialize_labels()

    def _initialize_entries(self):
        """Initialize entry fields for all four games."""
        entries = [[], [], [], []]
        for j in range(4):
            for i in range(5):
                validate_command = self.register(self.limit_characters)
                entry = tk.Entry(self, textvariable=self.entries_vars[i], width=2, validate='key',
                                 validatecommand=(validate_command, '%P'))
                entry.config(font=('Helvetica', 24), justify='center', bg='dark grey')
                entry.place(x=100 + (j % 2) * 400 + i * 70, y=150 + (j // 2) * 250)
                entry.bind('<KeyRelease>', self.tab_advance)
                entries[j].append(entry)
        return entries

    def _initialize_feedback_buttons(self):
        """Initialize feedback buttons for all four games."""
        feedback_buttons = [[], [], [], []]
        for j in range(4):
            for i in range(5):
                button = tk.Button(self, text='B', width=2, height=1, bg='dark grey')
                button.config(font=('Helvetica', 24))
                button.place(x=100 + (j % 2) * 400 + i * 70, y=200 + (j // 2) * 250)
                button.bind('<Button-1>', self.cycle_feedback)
                feedback_buttons[j].append(button)
        return feedback_buttons

    def _initialize_submit_button(self):
        """Initialize the submit button."""
        submit_button = tk.Button(self, text='Submit', command=self.submit)
        submit_button.place(x=350, y=650)

    def _initialize_labels(self):
        """Initialize result and possible guesses labels for all four games."""
        result_labels = []
        possible_guesses_labels = []
        for j in range(4):
            result_label = tk.Label(self, text='', bg='light grey')
            result_label.place(x=125 + (j % 2) * 350, y=270 + (j // 2) * 250)
            result_labels.append(result_label)

            possible_guesses_label = tk.Label(self, text='', bg='light grey')
            possible_guesses_label.place(x=125 + (j % 2) * 350, y=300 + (j // 2) * 250)
            possible_guesses_labels.append(possible_guesses_label)
        return result_labels, possible_guesses_labels

    def tab_advance(self, event):
        """Automatically move the cursor to the next field after a letter is entered."""
        event.widget.tk_focusNext().focus()

    def limit_characters(self, input):
        """Limit the entry input to a single character."""
        return len(input) <= 1

    def submit(self):
        """Submit the guesses and get optimal next guesses for all four games."""
        guessed_words = [''.join(entry.get().lower() for entry in entries) for entries in self.entries]
        feedbacks = [[button['text'] for button in feedback_buttons] for feedback_buttons in self.feedback_buttons]
        for i, solver in enumerate(self.solvers):
            solver.adjust_guess(guessed_words[i], feedbacks[i])
            optimal_guess = solver.get_optimal_guess()
            self.result_labels[i]['text'] = f'Optimal Guess: {optimal_guess}'
            self.guesses[i].append((guessed_words[i], feedbacks[i]))

            for entry, button in zip(self.entries[i], self.feedback_buttons[i]):
                entry.delete(0, tk.END)
                button['text'] = 'B'
                button['bg'] = 'dark grey'

            self.possible_guesses_labels[i]['text'] = f'Possible guesses remaining: {len(solver.possible_words)}'

    def cycle_feedback(self, event):
        """Cycle through feedback colors for a button."""
        current = event.widget['text']
        if current == 'B':
            event.widget['text'] = 'G'
            event.widget['bg'] = self.feedback_colors['G']
        elif current == 'G':
            event.widget['text'] = 'Y'
            event.widget['bg'] = self.feedback_colors['Y']
        else:
            event.widget['text'] = 'B'
            event.widget['bg'] = self.feedback_colors['B']

def main():
    app = QuordleGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
