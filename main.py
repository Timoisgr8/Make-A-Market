import pygame
import simpy
import threading
import sys
import random
import queue

# CONSTANTS
CARD_WIDTH = 360    # Width of each card
CARD_HEIGHT = 540   # Height of each card
GAP_X = 30          # Horizontal space between cards
GAP_Y = 30          # Vertical space between cards

CARD_VALUES = ['A', '2', '3', '4', '5',
               '6', '7', '8', '9', '10', 'J', 'Q', 'K']
CARD_SUITS = ['Hearts', 'Diamonds', 'Clubs', 'Spades']

# Map suits to rows
SUIT_TO_ROW = {
    "Spades": 0,
    "Hearts": 1,
    "Diamonds": 2,
    "Clubs": 3,
    "Hidden": 4,
}

# Initialize Pygame
pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Card Market Game")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 36)

# Game state
game_state = "menu"  # "menu" or "game"
input_text = ""
last_action_message = ""
current_round = 1
round_event_queue = queue.Queue()
number_of_cards = 4
max_rounds = 10
round_timer = 30 * 1000  # 30 seconds per round (in milliseconds)
game_over = False
show_realisation_cards = True
in_realisation_phase = False
realisation_timer = 0
player_score = 0
start_x = 50
start_y = 200
spacing = CARD_WIDTH // 3 + 10
tilemap = pygame.image.load("Card_Deck.png").convert_alpha()

current_bid = 0
current_ask = 0

class Button:
    def __init__(self, rect, label):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.color = (100, 100, 200)

    def draw(self, surface):
        pygame.draw.rect(surface, self.color, self.rect)
        draw_text(self.label, self.rect.x + 10, self.rect.y + 5)

    def is_clicked(self, pos):
        return self.rect.collidepoint(pos)

class Card:
    def __init__(self, value, suit):
        self.value = value
        self.suit = suit

    def __str__(self):
        return f"{self.value} of {self.suit}"


class Deck:
    def __init__(self):
        self.card_values = ["2", "3", "4", "5", "6",
                            "7", "8", "9", "10", "J", "Q", "K", "A"]
        self.card_suits = ["Diamonds", "Clubs", "Hearts", "Spades"]
        self.cards = [Card(value, suit)
                      for value in self.card_values for suit in self.card_suits]

    def shuffle(self):
        random.shuffle(self.cards)

    def draw_hand(self, n=5, allow_repeats=False):
        """Draw `n` cards from the deck.

        If allow_repeats is True, cards are drawn with replacement.
        If False, cards are removed from the deck.
        """
        if allow_repeats:
            return [random.choice(self.cards) for _ in range(n)]
        else:
            if n > len(self.cards):
                raise ValueError("Not enough cards left to draw that many.")
            hand = self.cards[:n]
            return hand

    def reset(self):
        self.__init__()

    def cards_remaining(self):
        return len(self.cards)

def extract_card_image(sheet, value, suit, scale_factor=3, card_width=CARD_WIDTH, card_height=CARD_HEIGHT, gap_x=GAP_X, gap_y=GAP_Y):
    """Extracts an individual card surface from the tilemap based on value and suit, scales it down by scale_factor"""
    try:
        col = CARD_VALUES.index(value)
        row = SUIT_TO_ROW[suit]
    except ValueError as e:
        raise ValueError(f"Invalid card: {value} of {suit}") from e

    x = col * (card_width + gap_x) + gap_x + 10
    y = row * (card_height + gap_y) + gap_y

    card_surface = pygame.Surface((card_width, card_height), pygame.SRCALPHA)
    card_surface.blit(sheet, (0, 0), (x, y, card_width, card_height))

    scaled_width = card_width // scale_factor
    scaled_height = card_height // scale_factor
    scaled_card_surface = pygame.transform.scale(
        card_surface, (scaled_width, scaled_height))

    return scaled_card_surface


def draw_text(text, x, y, color=(255, 255, 255)):
    img = font.render(text, True, color)
    screen.blit(img, (x, y))

def generate_bid_ask(target_value, variance=0.1, min_margin=2, max_margin=10):
    """
    Generates a bid and ask value based on the target value and a dynamic margin.
    
    target_value: The target card count (e.g., number of "K"s)
    variance: The standard deviation of the random spread for bid/ask
    min_margin: Minimum value for margin shrinkage
    max_margin: Maximum value for margin expansion
    """
    # Calculate the theoretical value of each hidden card (in your case, each hidden card has an EV of 8)
    num_hidden_cards = 3  # Example, you can adjust this based on actual game logic
    card_ev = 8
    theoretical_value = num_hidden_cards * card_ev

    # Randomly adjust the margin to shrink or expand it between the minimum and maximum values
    margin = random.randint(min_margin, max_margin)

    # Introduce some random shift to the margin (up or down) for realism
    shift = random.gauss(0, variance)  # Using Gaussian distribution for random shift

    # Apply the shift to the theoretical value
    adjusted_theoretical_value = theoretical_value + shift

    # Generate bid and ask values based on the adjusted theoretical value and margin
    ask = adjusted_theoretical_value + margin
    bid = adjusted_theoretical_value - margin

    # Ensure the bid and ask are positive
    ask = max(0, round(ask))
    bid = max(0, round(bid))
    
    return bid, ask

def start_new_round():
    global current_round, deck, revealed_cards, hidden_cards, round_timer, last_action_message, current_bid, current_ask

    deck.reset()
    deck.shuffle()
    hand = deck.draw_hand(number_of_cards, allow_repeats=False)

    target_value = "K"
    actual_count = sum(1 for card in revealed_cards + hidden_cards if card.value == target_value)

    # Generate bid and ask based on the actual count of the target cards
    current_bid, current_ask = generate_bid_ask(actual_count)

    # Simulate revealed and hidden cards for the round
    n_revealed = random.randint(0, 2)
    revealed_cards = hand[:n_revealed]
    hidden_cards = hand[n_revealed:]

    for card in revealed_cards:
        print(str(card))

    for card in hidden_cards:
        print(str(card))

    last_action_message = f"Round {current_round} started. {n_revealed} card(s) revealed."
    round_timer = 30 * 1000  # Set the round timer to 30 seconds (in milliseconds)

def draw_game_screen():
    global game_state
    game_state= "game"
  
    screen.fill((30, 30, 30))
    draw_text(f"Round: {current_round}", 50, 20)
    draw_text(f"Time Left: {round_timer // 1000}", 50, 60)
    draw_text(last_action_message, 50, 100)
    draw_text(f"Score: {player_score}", 50, 140)

    # Display bid and ask values
    draw_text(f"Bid: {current_bid}", 50, 200)
    draw_text(f"Ask: {current_ask}", 50, 240)

    # Draw revealed cards
    for i, card in enumerate(revealed_cards):
        card_img = extract_card_image(tilemap, card.value, card.suit)
        x = start_x + i * spacing
        screen.blit(card_img, (x, start_y))

    # Draw hidden cards (with placeholder back)
    for j, _ in enumerate(hidden_cards):
        placeholder = extract_card_image(tilemap, "5", "Hidden")  # placeholder
        x = start_x + (len(revealed_cards) + j) * spacing
        screen.blit(placeholder, (x, start_y))

    # Draw buttons
    for btn in amount_buttons:
        btn.draw(screen)
    bid_button.draw(screen)
    ask_button.draw(screen)

def handle_game_events(event):
    global amount_selected, game_state, current_round, last_action_message
    global realisation_timer

    if event.type == pygame.MOUSEBUTTONDOWN:
        pos = event.pos

        for btn in amount_buttons:
            if btn.is_clicked(pos):
                amount_selected = int(btn.label)
                last_action_message = f"Selected amount: {amount_selected}"

        if bid_button.is_clicked(pos):
            evaluate_realisation("bid")
            game_state = "realisation"
            realisation_timer = 5000 

        if ask_button.is_clicked(pos):
            evaluate_realisation("ask")
            game_state = "realisation"
            realisation_timer = 5000

def evaluate_realisation(action):
    global last_action_message, player_score

    # Count how many target cards are in the full hand
    target_value = "K"  # or whatever is your target
    actual_count = sum(1 for card in revealed_cards +
                       hidden_cards if card.value == target_value)

    correct = False
    gain = 0

    if action == "bid":
        if actual_count >= amount_selected:
            correct = True
            gain = 100 * amount_selected
        else:
            gain = -50
    elif action == "ask":
        if actual_count < amount_selected:
            correct = True
            gain = 50 * (amount_selected - actual_count)
        else:
            if actual_count == amount_selected:
                gain = -50
            else:
                gain = -50 - 50 * (actual_count - amount_selected)

    player_score += gain
    last_action_message = f"Actual {target_value}s: {actual_count}. {'Correct' if correct else 'Wrong'}. {'Gained' if gain >= 0 else 'Lost'} {abs(gain)}."


def draw_realisation_screen():  
    screen.fill((30, 30, 30))
    draw_text(f"Realisation Phase — Round {current_round}", 50, 20)
    draw_text(last_action_message, 50, 60)
    draw_text(f"Score: {player_score}", 50, 100)

    if show_realisation_cards:
        cards_to_show = revealed_cards + hidden_cards
    else:
        cards_to_show = [Card("5", "Hidden") for _ in revealed_cards + hidden_cards]

    for i, card in enumerate(cards_to_show):
        card_img = extract_card_image(tilemap, card.value, card.suit)
        x = start_x + i * spacing
        screen.blit(card_img, (x, start_y))

    # Adjusting rectangle position to be next to the text
    draw_text("Enter your gain/loss:", 50, 500)

    # Position the rectangle to the right of the text
    rect_x = 325  # 50 is the starting X position of the text + a margin for spacing
    rect_y = 500 - 5   # Align the rectangle vertically with the text (add a little offset for better alignment)

    pygame.draw.rect(screen, (200, 200, 200), (rect_x, rect_y, 140, 40))

    # Now draw the input text inside the rectangle
    draw_text(input_text, rect_x + 10, rect_y + 5, color=(0, 0, 0))  # Add padding for the input text


input_amount = ""
amount_selected = 1

amount_buttons = [
    Button((600, 100, 60, 40), "1"),
    Button((600, 150, 60, 40), "5"),
    Button((600, 200, 60, 40), "10")
]

bid_button = Button((600, 300, 80, 40), "Bid")
ask_button = Button((700, 300, 80, 40), "Ask")

deck = Deck()

# === Main loop ===
running = True
start_ticks = pygame.time.get_ticks()

revealed_cards = []
hidden_cards = []
start_new_round()

while running:
    dt = clock.tick(60)
    round_timer -= dt

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        # MENU PHASE
        if game_state == "menu":
            if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                game_state = "game"
                last_action_message = "Game Started!"
                start_new_round()

        # GAME PHASE
        elif game_state == "game":
            handle_game_events(event)

        # INPUT PHASE (after realisation screen hides cards)
        elif game_state == "realisation":
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_BACKSPACE:
                    input_text = input_text[:-1]
                elif event.key == pygame.K_RETURN:
                    try:
                        typed_gain = int(input_text)
                        # Optionally compare with actual gain for feedback
                        last_action_message = f"You entered {typed_gain}."
                    except ValueError:
                        last_action_message = "Invalid input! Please enter a number."
                    else:
                        input_text = ""
                        current_round += 1
                        if current_round >= max_rounds:
                            game_state = "game_over"
                        else:
                            game_state = "game"
                            start_new_round()
                else:
                    input_text += event.unicode

    # PHASE LOGIC / DRAWING
    if game_state == "menu":
        screen.fill((0, 0, 0))
        draw_text("Press ENTER to start the Card Market Game", 150, 250)

    elif game_state == "game":
        draw_game_screen()

    if game_state == "realisation":
        realisation_timer -= dt

        if realisation_timer <= 0:
            show_realisation_cards = True
        draw_realisation_screen()
        
    elif game_state == "game_over":
        screen.fill((0, 0, 0))
        draw_text("Game Over!", 300, 250)
        draw_text(f"Final Score: {player_score}", 300, 300)
        draw_text("Press ENTER to return to Menu", 300, 350)

    pygame.display.flip()
    
pygame.quit()
sys.exit()
