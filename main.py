import pygame
import random
import sys
from collections import defaultdict

# CONSTANTS
CARD_WIDTH = 360    # Width of each card
CARD_HEIGHT = 540   # Height of each card
GAP_X = 30          # Horizontal space between cards
GAP_Y = 30          # Vertical space between cards

CARD_VALUES = ['A', '2', '3', '4', '5',
               '6', '7', '8', '9', '10', 'J', 'Q', 'K']
CARD_SUITS = ['Hearts', 'Diamonds', 'Clubs', 'Spades']

# Card values mapping (A=14, K=13, Q=12, J=11, 10=10, etc.)
CARD_VALUE_MAP = {
    'A': 14,
    'K': 13,
    'Q': 12,
    'J': 11,
    '10': 10,
    '9': 9,
    '8': 8,
    '7': 7,
    '6': 6,
    '5': 5,
    '4': 4,
    '3': 3,
    '2': 2
}

# Map suits to rows
SUIT_TO_ROW = {
    "Spades": 0,
    "Hearts": 1,
    "Diamonds": 2,
    "Clubs": 3,
    "Hidden": 4,
}

ROUND_EVENTS = [
    ("Normal Round", None),
    ("Card Ace is worth 20 this round", lambda c: 20 if c.value == 'A' else c.numeric_value),
    ("Card King is worth 15 this round", lambda c: 15 if c.value == 'K' else c.numeric_value),
    ("Only cards worth 10+ count this round", lambda c: c.numeric_value if c.numeric_value >= 10 else 0),
    ("Only cards worth 7 or less count this round", lambda c: c.numeric_value if c.numeric_value <= 7 else 0),
    ("Only even cards count this round", lambda c: c.numeric_value if c.numeric_value % 2 == 0 else 0),
    ("Only odd cards count this round", lambda c: c.numeric_value if c.numeric_value % 2 != 0 else 0),
    ("Only red cards count this round", lambda c: c.numeric_value if c.suit in ['Hearts', 'Diamonds'] else 0),
    ("Only black cards count this round", lambda c: c.numeric_value if c.suit in ['Clubs', 'Spades'] else 0),
    ("All cards doubled this round", lambda c: c.numeric_value * 2),
    ("Face cards (J,Q,K) worth 5 extra", lambda c: c.numeric_value + 5 if c.value in ['J', 'Q', 'K'] else c.numeric_value)
]

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
number_of_cards = 4
max_rounds = 10
round_timer = 30 * 1000  # 30 seconds per round (in milliseconds)
game_over = False
show_realisation_cards = True
in_realisation_phase = False
realisation_timer = 0
# Add to game state variables
current_event = None
event_modifier = None

player_score = 0
start_x = 50
start_y = 250
spacing = CARD_WIDTH // 3 + 10
tilemap = pygame.image.load("Card_Deck.png").convert_alpha()
current_bid = 0
current_ask = 0
option = ""
actual_gain = 0
total_card_value = 0  # Sum of all card values in current round


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
        self.numeric_value = CARD_VALUE_MAP[value]

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


def generate_bid_ask(event_name):
    """
    Generates bid/ask prices that account for round events
    """
    base_value = 24  # Default theoretical value
    
    # Adjust base value based on event
    if "Ace is worth 20" in event_name:
        base_value += (20-14)  # Ace normally 14, now 20
    elif "King is worth 15" in event_name:
        base_value += (15-13)  # King normally 13, now 15
    elif "10+" in event_name:
        base_value = 18  # Lower expected value since only high cards count
    elif "7 or less" in event_name:
        base_value = 12  # Lower expected value
    elif "doubled" in event_name:
        base_value *= 2
    elif "Face cards" in event_name:
        base_value += 3  # Slightly higher expected value
    
    # 70% chance favorable, 30% unfavorable
    if random.random() < 0.7:  # Favorable
        spread = random.uniform(1, 2)
        bid = base_value + spread
        ask = base_value - spread
    else:  # Unfavorable
        spread = random.uniform(3, 5)
        bid = base_value + spread * 1.5
        ask = base_value - spread * 1.5
    
    # Ensure minimum values and bid > ask
    bid = max(10, round(bid))
    ask = max(5, round(ask))
    if bid <= ask:
        bid = ask + 1
    
    return bid, ask


def start_new_round():
    global current_round, deck, revealed_cards, hidden_cards, round_timer, last_action_message
    global current_bid, current_ask, total_card_value, amount_selected, current_event, event_modifier

    amount_selected = 0

    deck.reset()
    deck.shuffle()
    hand = deck.draw_hand(number_of_cards, allow_repeats=False)

    # Select random round event (30% chance for special event)
    if random.random() < 0.3 and current_round > 1:  # Skip event on first round
        current_event, event_modifier = random.choice(ROUND_EVENTS[1:])  # Skip normal round
    else:
        current_event, event_modifier = ROUND_EVENTS[0]  # Normal round
    
    # Apply event modifier to calculate total value
    if event_modifier:
        total_card_value = sum(event_modifier(card) for card in hand)
    else:
        total_card_value = sum(card.numeric_value for card in hand)

    # Generate bid and ask values based on event
    current_bid, current_ask = generate_bid_ask(current_event)

    # Simulate revealed and hidden cards
    n_revealed = random.randint(0, 2)
    revealed_cards = hand[:n_revealed]
    hidden_cards = hand[n_revealed:]

    last_action_message = f"Round {current_round}"
    round_timer = 30 * 1000



def draw_game_screen():
    global game_state
    game_state = "game"

    screen.fill((30, 30, 30))
    draw_text(f"Round: {current_round}", 50, 20)
    draw_text(f"Time Left: {round_timer // 1000}", 50, 60)
    draw_text(last_action_message, 50, 100)
    draw_text(f"Score: {player_score}", 50, 140)

    draw_text(f"Event: {current_event}", 50, 180)

    # Display bid and ask values
    draw_text(f"Bid: {current_bid}", 200, 500)
    draw_text(f"Ask: {current_ask}", 300, 500)

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
    global realisation_timer, show_realisation_cards, input_text, option, actual_gain

    if event.type == pygame.MOUSEBUTTONDOWN:
        pos = event.pos

        for btn in amount_buttons:
            if btn.is_clicked(pos):
                amount_selected = int(btn.label)
                last_action_message = f"Selected amount: {amount_selected}"

        if bid_button.is_clicked(pos):
            game_state = "realisation"
            realisation_timer = 3000  # 3 seconds in milliseconds
            show_realisation_cards = True
            option = "bid"
            actual_gain = evaluate_realisation("bid")
            input_text = ""  # Reset input for new round
            # print(f"Round {current_round} - Bid Evaluation: Gain/Loss: {actual_gain}")
                    
        if ask_button.is_clicked(pos):
            game_state = "realisation"
            realisation_timer = 3000  # 3 seconds in milliseconds
            show_realisation_cards = True
            option = "ask"
            actual_gain = evaluate_realisation("ask")
            input_text = ""  # Reset input for new round
            # print(f"Round {current_round} - Ask Evaluation: Gain/Loss: {actual_gain}")


def evaluate_realisation(action):
    global last_action_message, player_score, current_round, total_card_value

    # Calculate the actual value using event modifier if exists
    if event_modifier:
        actual_value = sum(event_modifier(card) for card in revealed_cards + hidden_cards)
    else:
        actual_value = sum(card.numeric_value for card in revealed_cards + hidden_cards)

    gain = 0
    explanation = ""

    if action == "bid":
        gain = amount_selected * (actual_value - current_bid)
    elif action == "ask":
        gain = amount_selected * (current_ask - actual_value)

    last_action_message = explanation
    return gain


def draw_realisation_screen():  
    global show_realisation_cards, realisation_timer, current_round, game_state, input_text
    
    screen.fill((30, 30, 30))
    draw_text(f"Realisation Phase — Round {current_round}", 50, 20)
    draw_text(last_action_message, 50, 60)
    
    # Show the bid/ask value that was priced
    if option == "bid":
        draw_text(f"You bid for {amount_selected} at {current_bid} each", 50, 100)
    else:
        draw_text(f"You asked for {amount_selected} at {current_ask} each", 50, 100)

    draw_text(f"Score: {player_score}", 50, 140)

    # Handle card visibility timer
    if realisation_timer > 0:
        show_realisation_cards = True
    else:
        show_realisation_cards = False

    # Draw cards - either revealed or hidden based on timer
    if show_realisation_cards:
        cards_to_show = revealed_cards + hidden_cards
    else:
        cards_to_show = [Card("5", "Hidden") for _ in revealed_cards + hidden_cards]

    for i, card in enumerate(cards_to_show):
        card_img = extract_card_image(tilemap, card.value if show_realisation_cards else "5", 
                                    card.suit if show_realisation_cards else "Hidden")
        x = start_x + i * spacing
        screen.blit(card_img, (x, start_y))

    draw_text("Enter your gain/loss:", 50, 500)
    rect_x = 325
    rect_y = 500 - 5
    pygame.draw.rect(screen, (200, 200, 200), (rect_x, rect_y, 140, 40))
    draw_text(input_text, rect_x + 10, rect_y + 5, color=(0, 0, 0))


input_amount = ""
amount_selected = 0

amount_buttons = [
    Button((600, 200, 60, 40), "0"),
    Button((700, 200, 60, 40), "1"),
    Button((600, 250, 60, 40), "5"),
    Button((700, 250, 60, 40), "10")
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
    
    if game_state == "game":
        round_timer -= dt
        if round_timer <= 0:
            round_timer = 0
            game_state = "realisation"
            realisation_timer = 3000
            show_realisation_cards = True
            actual_gain = 0  # Timeout results in 0 gain
            input_text = ""

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

        # REALISATION PHASE - Handle input here
        elif game_state == "realisation":
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_BACKSPACE:
                    input_text = input_text[:-1]
                elif event.key == pygame.K_RETURN:
                    try:
                        player_input = int(input_text)
                        # Compare with actual gain
                        if player_input == actual_gain:
                            # Correct input - apply the gain/loss
                            player_score += actual_gain
                            last_action_message = f"Correct! {actual_gain} applied to your score."
                            print(f"Round {current_round} - Player input CORRECT: {player_input} | Score change: {actual_gain} | New score: {player_score}")
                        else:
                            # Incorrect input - apply penalties
                            if actual_gain >= 0:
                                # Player missed a gain - lose 50
                                player_score -= 50
                                last_action_message = f"Incorrect! You missed a gain of {actual_gain}. Penalty: -50."
                                print(f"Round {current_round} - Player input INCORRECT (missed gain) | Expected: {actual_gain} | Entered: {player_input} | Penalty: -50 | New score: {player_score}")
                            else:
                                # Player underreported a loss - absorb full loss plus 50
                                player_score += actual_gain - 50
                                last_action_message = f"Incorrect! You underreported a loss of {abs(actual_gain)}. Penalty: full loss plus -50."
                                print(f"Round {current_round} - Player input INCORRECT (underreported loss) | Expected: {actual_gain} | Entered: {player_input} | Penalty: {actual_gain - 50} | New score: {player_score}")
                        
                        # Move to next round or end game
                        current_round += 1
                        if current_round > max_rounds:
                            game_state = "game_over"
                        else:
                            start_new_round()
                            game_state = "game"
                    except ValueError:
                        last_action_message = "Invalid input! Please enter a number."
                        print(f"Round {current_round} - INVALID INPUT: '{input_text}' is not a number")
                else:
                    if event.unicode.isdigit() or (event.unicode == "-" and input_text == ""):
                        input_text += event.unicode

    # PHASE LOGIC / DRAWING
    if game_state == "menu":
        screen.fill((0, 0, 0))
        draw_text("Press ENTER to start the Card Market Game", 150, 250)

    elif game_state == "game":
        draw_game_screen()

    elif game_state == "realisation":
        if realisation_timer > 0:
            realisation_timer -= dt
            show_realisation_cards = True

        if realisation_timer <= 0:
            show_realisation_cards = False
        draw_realisation_screen()
        
    elif game_state == "game_over":
        screen.fill((0, 0, 0))
        draw_text("Game Over!", 300, 250)
        draw_text(f"Final Score: {player_score}", 300, 300)
        draw_text("Press ENTER to return to Menu", 300, 350)
        
        # Check for ENTER key to return to menu
        keys = pygame.key.get_pressed()
        if keys[pygame.K_RETURN]:
            game_state = "menu"
            current_round = 1
            player_score = 0
            start_new_round()

    pygame.display.flip()
    
pygame.quit()
sys.exit()