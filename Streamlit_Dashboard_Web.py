import streamlit as st
import streamlit.components.v1 as components  
import sqlite3
import pandas as pd
import plotly.express as px
import chess
import chess.svg
import os
import sys
import re
import requests  
import glob

if 'active_db' not in st.session_state:
    # 1. Check if your Dashboard_Launcher passed a specific database
    if len(sys.argv) > 1 and sys.argv[1].endswith('.db'):
        # THIS IS THE FIX: Strip out the C:/Sqlite/ folder path!
        st.session_state.active_db = os.path.basename(sys.argv[1]) 
    else:
# 2. Otherwise, automatically find the newest
        db_files = glob.glob("databases/*.db")
        if db_files:
            newest_db = max(db_files, key=os.path.getmtime)
            st.session_state.active_db = os.path.basename(newest_db)
        else:
            st.session_state.active_db = 'FIDE WSTC 2025.db'




def get_game_lessons_dict(game_id, current_db_name):
    """Parses the text file and returns a dictionary of {move_number: lesson_text}"""
    # 1. Build the target file name
    base_name = current_db_name.replace('.db', '').replace(' - ', ' ')
    file_path = f"data/Automated_Detailed_Analysis - {base_name}.txt"
    
    lesson_dict = {}
    
    if not os.path.exists(file_path):
        return lesson_dict
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 2. Split into individual lessons
        chunks = content.split('==================================================')
        search_target = f"| GAME ID: {game_id}\n"
        
        for chunk in chunks:
            if search_target in chunk:
                # 3. Find the move number right under [THE CRITICAL ERROR]
                match = re.search(r'\[THE CRITICAL ERROR\]\s*Move:\s*(\d+)', chunk)
                if match:
                    move_num = int(match.group(1))
                    # Add it to our lookup dictionary!
                    if move_num not in lesson_dict:
                        lesson_dict[move_num] = chunk.strip()
                        
    except Exception as e:
        print(f"Error reading analysis file: {e}")
        
    return lesson_dict
#
# Load Game Synopsis Dictionary
def load_synopses_dict(current_db_name):
    """Reads the generated synopses text file and returns a dictionary."""
    base_name = current_db_name.replace('.db', '')
    file_path = f"data/Game_Synopses - {base_name}.txt"
    
    synopses_data = {}
    if not os.path.exists(file_path):
        return synopses_data 
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        chunks = content.split('==================================================')
        
        for chunk in chunks:
            if not chunk.strip():
                continue
            lines = chunk.strip().split('\n')
            game_id, blunders, synopsis = "", "", ""
            
            for line in lines:
                if line.startswith("| GAME ID:"):
                    game_id = line.split(":", 1)[1].strip()
                elif line.startswith("| BLUNDERS:"):
                    blunders = line.split(":", 1)[1].strip()
                elif line.startswith("| SYNOPSIS:"):
                    synopsis = line.split(":", 1)[1].strip()
                    
            if game_id:
                synopses_data[game_id] = {"blunders": blunders, "synopsis": synopsis}
                
    except Exception as e:
        pass # Silently fail if there's a file reading glitch
        
    return synopses_data
    
#  IMPORT PLAYER ROSTER from EXCEL


@st.cache_data
def load_player_roster(file_path="data/Player_Roster.xlsx"):
    try:
        if os.path.exists(file_path):
            df = pd.read_excel(file_path)
            # Force all names to lowercase in our "lookup dictionary" so case doesn't matter
            names = df['Name'].astype(str).str.strip().str.lower()
            ids = df['USCF_ID'].astype(str).str.replace('.0', '', regex=False)
            return dict(zip(names, ids))
        return {}
    except Exception as e:
        print(f"Roster load error: {e}")
        return {}

player_roster = load_player_roster()

def make_clickable_name(raw_player_name):
    """Sanitizes the name, matches it, and makes it a beautiful clickable link."""
   # Instead of fancy regex, just chop off EVERYTHING from the first '(' onwards!
    clean_name = str(raw_player_name).split('(')[0].strip()
    
    # 2. Convert to lowercase to check our invisible roster dictionary
    lookup_name = clean_name.lower()
    
    # 3. Format the name nicely for the screen (e.g., "STEPHEN" -> "Stephen")
    display_name = clean_name.title()
    
    # 4. Make it a link if we found them!
    if lookup_name in player_roster:
        uscf_id = player_roster[lookup_name]
        return f"[{display_name}](https://ratings.uschess.org/player/{uscf_id})"
    
    return display_name

# --- 1. Page Configuration & Custom CSS ---
st.set_page_config(page_title="Chess Learning Lab", page_icon="♟️", layout="wide")



st.markdown("""
    <style>
    button[kind="primary"] {
        background-color: white !important;
        color: black !important;
        border: 1px solid black !important;
        font-weight: bold !important;
    }
    button[kind="primary"]:hover {
        background-color: #f0f0f0 !important;
        border-color: gray !important;
    }
    </style>
""", unsafe_allow_html=True)
#
# --- 2. Database Loading Functions ---
DATA_DIR = "."

@st.cache_data
def get_database_files():
    """Finds all SQLite databases in the target folder."""
    if os.path.exists(DATA_DIR):
        files = glob.glob(os.path.join(DATA_DIR, "databases/*.db"))
        return [os.path.basename(f) for f in files]
    return []

def load_ai_synopsis(db_filename):
    """Reads the AI synopsis text file that matches the current database."""
    base_name = db_filename.replace(".db", "")
    target_txt_file = f"data/Club_Mega_Trends_Synopsis_{base_name}.txt"
    full_path = os.path.join(DATA_DIR, target_txt_file)
    
    try:
        with open(full_path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return f"⚠️ The AI Synopsis file '{target_txt_file}' was not found in {DATA_DIR}."


# --- NEW: Textbook FEN Reference Dictionaries ---
TEXTBOOK_STRUCTURES = {
    "Lopez Formation": "8/pp3ppp/3p4/2p1p3/3PP3/2P5/PP3PPP/8 w - - 0 1",
    "Closed Ruy Lopez": "8/p4ppp/3p4/1p1Pp3/2p1P3/2P5/PP3PPP/8 w - - 0 1",
    "Panov": "8/pp2pppp/8/2Pp4/3P4/8/PP3PPP/8 w - - 0 1",
    "Scheveningen Variation": "8/pp3ppp/3pp3/8/4P3/8/PPP2PPP/8 w - - 0 1",
    "Dragon": "8/pp2pp1p/3p2p1/8/4P3/8/PPP2PPP/8 w - - 0 1",
    "Benko Structure": "8/4pp1p/3p2p1/2pP4/4P3/8/PP3PPP/8 w - - 0 1",
    "Symmetric Benoni": "8/pp3ppp/3p4/2pP4/2P5/8/PP3PPP/8 w - - 0 1",
    "Najdorf Type I": "8/pp3ppp/3p4/3Pp3/8/8/PPP2PPP/8 w - - 0 1",
    "Stonewall Formation": "8/ppp3pp/4p3/3p1p2/3P4/8/PPP1PPPP/8 w - - 0 1",
    "Hedgehog Formation": "8/5ppp/pp1pp3/8/2P1P3/8/PP3PPP/8 w - - 0 1",
    "Najdorf Type II": "8/pp3ppp/3p4/4p3/4P3/8/PPP2PPP/8 w - - 0 1",
    "Carlsbad Formation": "8/ppp2ppp/8/3p4/3P4/4P3/PP3PPP/8 w - - 0 1",
    "Slav Formation": "8/pp3ppp/2p1p3/8/3P4/4P3/PP3PPP/8 w - - 0 1",
    "Isolani": "8/pp3ppp/4p3/8/3P4/8/PP3PPP/8 w - - 0 1",
    "Asymmetric Benoni": "8/pp3ppp/3p4/2pP4/4P3/8/PP3PPP/8 w - - 0 1",
    "Maroczy Bind": "8/pp2pp1p/3p2p1/8/2P1P3/8/PP3PPP/8 w - - 0 1",
    "Grunfeld Center": "8/pp2pppp/8/2p5/3PP3/2P5/P4PPP/8 w - - 0 1",
    "Caro-Kann": "8/pp3ppp/2p1p3/8/3P4/2P5/PP3PPP/8 w - - 0 1",
    "Hanging Pawns": "8/pp3ppp/4p3/8/2PP4/8/P4PPP/8 w - - 0 1",
    "KID Type I": "8/pp3ppp/3p4/3Pp3/4P3/8/PP3PPP/8 w - - 0 1",
    "French Type I": "8/ppp3pp/4p3/3p4/3P4/8/PPP2PPP/8 w - - 0 1",
    "KID Type II": "8/pp3ppp/3p4/2pPp3/2P1P3/8/PP3PPP/8 w - - 0 1",
    "KID Complex": "8/pp3ppp/2pp4/4p3/2PPP3/8/PP3PPP/8 w - - 0 1",
    "KID Type III": "8/ppp2ppp/3p4/3Pp3/2P1P3/8/PP3PPP/8 w - - 0 1",
    "Open KID": "8/ppp2ppp/3p4/8/2P1P3/8/PP3PPP/8 w - - 0 1",
    "French Type II": "8/pp3ppp/4p3/3pP3/8/2P5/PP3PPP/8 w - - 0 1",
    "French Type III": "8/ppp2ppp/4p3/3pP3/3P4/8/PPP2PPP/8 w - - 0 1",
    "3 vs 3 and 4 vs 3 Structure": "8/pp3ppp/4p3/8/8/2P5/PP3PPP/8 w - - 0 1"
}

POLGAR_THEMES = {
    "1. Epaulet mate": {"fen": "3rkr2/8/8/8/8/8/8/4Q1K1 w - - 0 1", "explanation": "White plays Qe7#. The Black King is trapped by its own Rooks on d8 and f8, which act as 'epaulets' (shoulder ornaments), preventing the King from escaping."},
    "2. Back rank": {"fen": "6k1/5ppp/8/8/8/8/8/4R1K1 w - - 0 1", "explanation": "White plays Re8#. This is the classic corridor mate. The Black King is trapped on the back rank by its own protective pawn shield."},
    "3. Double attack": {"fen": "2q3k1/5ppp/8/3N4/8/8/8/1K6 w - - 0 1", "explanation": "White plays Ne7+. This is a true, forced Knight fork. The Knight safely checks the Black King on g8 and simultaneously attacks the undefended Black Queen on c8."},
    "4. Deflection": {"fen": "3r2k1/p2r1ppp/8/8/8/2Q5/P4PPP/3R2K1 w - - 0 1", "explanation": "White plays Rxd7. The Black Rook on d8 is currently defending the back rank. If Black recaptures with ...Rxd7, the Rook is deflected from its defensive duty, allowing White to play Qc8+ and force mate."},
    "5. Decoy": {"fen": "2q3k1/5ppp/8/3N4/8/8/8/R5K1 w - - 0 1", "explanation": "White plays Ra8!. The Black Queen is forced (decoyed) to capture the Rook (...Qxa8). By doing so, the Queen steps onto the exact square needed for White to play the devastating fork Ne7+."},
    "6. Clearance": {"fen": "6k1/1p3ppp/8/4P3/8/2Q5/8/6K1 w - - 0 1", "explanation": "White plays e6!. By sacrificing the pawn, White forcefully clears the c3-g7 diagonal for the Queen. If Black plays ...fxe6, White delivers mate with Qxg7#."},
    "7. Discovered attack": {"fen": "3q2k1/5ppp/8/8/8/3B4/3R4/6K1 w - - 0 1", "explanation": "White plays Bxh7+. The Bishop moves out of the way with a forced check, intentionally 'discovering' a hidden attack from the White Rook on d2 against the unprotected Black Queen on d8."},
    "8. Opening up the diagonal": {"fen": "7k/1p3ppp/8/8/8/8/3P4/B2Q2K1 w - - 0 1", "explanation": "White plays d4. This simple pawn push permanently opens the a1-h8 long diagonal, activating the White Bishop and aiming it directly at the Black Kingside."},
    "9. Long diagonal": {"fen": "7k/1p4pp/8/8/8/8/1Q4PP/B5K1 w - - 0 1", "explanation": "A textbook illustration of absolute domination on the a1-h8 long diagonal. The combined battery of the Queen and Bishop is threatening an unstoppable mate on g7."},
    "10. Opening up a line": {"fen": "3q2k1/5ppp/8/8/8/8/3P4/3R2K1 w - - 0 1", "explanation": "White plays d4 (and eventually d5). By pushing and trading the central pawn, White forces the d-file to open up, giving the Rook on d1 a direct line of attack against the Black Queen."},
    "11. Open line": {"fen": "3r2k1/5ppp/8/8/8/8/8/3R2K1 w - - 0 1", "explanation": "An open line is a file with no pawns on it. Here, both players have correctly placed their Rooks on the fully open d-file to fight for control of the board."},
    "12. Closing a line": {"fen": "3q2k1/5ppp/8/4P3/8/8/1Q4PP/6K1 w - - 0 1", "explanation": "Often called 'Interference'. The White pawn on e5 acts as a physical barrier, closing the 5th rank and the long diagonal, preventing the Black Queen from defending critical squares on the Kingside."},
    "13. Pin": {"fen": "3q2k1/5ppp/8/3n4/8/8/8/3R2K1 w - - 0 1", "explanation": "The Black Knight on d5 is 'absolutely pinned'. It cannot legally move, because doing so would expose the Black Queen on d8 to capture by the White Rook on d1."},
    "14. Rook on the 7th rank": {"fen": "7k/1R4pp/8/8/8/8/8/6K1 w - - 0 1", "explanation": "The classic 'Pig on the 7th'. A Rook on the 7th rank is incredibly powerful because it traps the enemy King on the back rank and easily munches on undefended pawns."},
    "15. Sacrifice on h7": {"fen": "r1bq1rk1/pppp1ppp/2n5/4p3/4P3/3B1N2/PPPP1PPP/R1BQ1RK1 w - - 0 1", "explanation": "The setup for the classic 'Greek Gift' sacrifice. White plays Bxh7+, sacrificing the Bishop to rip open the Black King's defenses, followed by Ng5+ and Qh5."},
    "16. Sacrifice on h6": {"fen": "r1bq1rk1/pppp1p1p/2n3p1/4p3/4P3/3B1N1Q/PPPP1PPP/R1B2RK1 w - - 0 1", "explanation": "White's pieces are aimed at the weakened dark squares around the Black King. A sacrifice on h6 (often a Bishop) is used to completely shatter a fianchettoed or weakened Kingside."},
    "17. Sacrifice on g7": {"fen": "r1bq1rk1/pppp1ppp/2n5/4p3/4P3/3B1N2/PPPP1PPP/R1B2RK1 w - - 0 1", "explanation": "A direct assault on the square directly in front of the castled King. Sacrificing on g7 removes the King's primary pawn shield."},
    "18. Sacrifice on g6": {"fen": "r1bq1rk1/pppp1ppp/2n3p1/4p3/4P3/3B1N2/PPPP1PPP/R1B2RK1 w - - 0 1", "explanation": "Black has weakened the Kingside by pushing the g-pawn. A sacrifice on g6 exploits this specific structural weakness to open lines for the heavy pieces."},
    "19. Sacrifice on f7": {"fen": "r1bqk2r/pppp1ppp/2n5/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 0 1", "explanation": "The most common target in the opening and early middlegame. The f7 pawn is uniquely weak because it is defended only by the King. White plays Bxf7+ to draw the King into the center."},
    "20. Sacrifice on f6": {"fen": "r1bq1rk1/pppp1ppp/2n2n2/4p3/4P3/3B1N2/PPPP1PPP/R1B2RK1 w - - 0 1", "explanation": "The Knight on f6 is the primary defender of the castled King (guarding h7). Sacrificing an exchange or a piece on f6 destroys the King's best bodyguard."},
    "21. Attack against the kingside": {"fen": "r1bqr1k1/ppp2ppp/2n5/3pP3/3P4/3B1N2/PP1Q1PPP/R4RK1 w - - 0 1", "explanation": "White has heavily concentrated pieces (the Bishop on d3, Queen on d2, and Knight on f3) aiming directly at the castled Black Kingside, preparing for a devastating assault."},
    "22. Hunting the king": {"fen": "r1bq3r/pppp1kpp/2n5/4P3/1bQ5/5N2/PB3PPP/R4RK1 b - - 0 1", "explanation": "White has played Qc4+, forcing the uncastled Black King to wander further out into the center of the board where it can be ruthlessly hunted by the remaining pieces."},
    "23. Annihilation of the defensive piece": {"fen": "6k1/5ppp/8/8/4b3/8/1Q6/4R1K1 w - - 0 1", "explanation": "White plays Rxe4! The Black Bishop was the only piece defending the back rank from mate. By sacrificing the exchange to annihilate the defender, White forces ...fxe4, followed by Qb8#."},
    "24. King in the middle": {"fen": "r1bqk2r/pppp1ppp/2n2n2/4p3/1bB1P3/2NP1N2/PPP2PPP/R1BQK2R b KQkq - 0 1", "explanation": "Black's King is still sitting on its starting square in the dead center of the board, making it highly vulnerable to a central breakthrough by White."},
    "25. March with the king": {"fen": "8/8/8/8/4k3/4P3/4K3/8 w - - 0 1", "explanation": "In the endgame, the King becomes an active attacking piece. Here, the Kings are in opposition, and White must carefully march their King to escort the pawn to promotion."},
    "26. Opposite side castling": {"fen": "2kr1b1r/pppq1ppp/2np1n2/4p3/4P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 1", "explanation": "White has castled Kingside, while Black has castled Queenside. This usually leads to fierce pawn storms as both players attack the enemy King without weakening their own."},
    "27. Counter attack": {"fen": "3r2k1/p4ppp/8/8/4Q3/8/1q3PPP/4R1K1 b - - 0 1", "explanation": "Black is threatened with a devastating back-rank mate (Re8#). However, Black ignores the threat and launches a sudden, lethal counter-attack with ...Qc1+ or ...Qxf2+!"},
    "28. Defence": {"fen": "6k1/1Q3ppp/8/8/8/8/5PPP/6K1 b - - 0 1", "explanation": "Sometimes you just have to hold the line. Black must accurately defend against White's immediate, game-ending threat of Qg7#."},
    "29. Attack with pawns": {"fen": "2kr1b1r/pp1q1ppp/2np1n2/2p1p3/2P1P1P1/2NP1N2/PP3P1P/R1BQK1R1 w Q - 0 1", "explanation": "A classic 'Pawn Storm'. White is violently pushing the g-pawn and h-pawn up the board to rip open Black's castled King position."},
    "30. Pawn breakthrough": {"fen": "8/1p3p2/p3p3/P2pP3/1P1P4/8/8/4K1k1 w - - 0 1", "explanation": "A typical endgame tactic where a player pushes and sacrifices one or more pawns (e.g., playing b5!) to force a single pawn through the enemy blockade to promote to a Queen."},
    "31. Pawn hunt": {"fen": "8/8/8/8/4k3/8/4P3/4K3 w - - 0 1", "explanation": "The active piece (often a King or Rook in the endgame) systematically hunts down and captures the opponent's weak, undefended pawns one by one."},
    "32. Advantage in development": {"fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1", "explanation": "White has three pieces developed and is ready to castle. Black only has two pieces out. White's rapid development gives them the early initiative."},
    "33. Positional pawn sacrifice": {"fen": "r1bq1rk1/ppp1nppp/3p4/4P3/2B5/2P2N2/P4PPP/R2QR1K1 w - - 0 1", "explanation": "White intentionally gives up a pawn not for a direct tactical checkmate, but to gain permanently open lines, better squares for their pieces, and long-term pressure."},
    "34. Positional exchange sacrifice": {"fen": "r1bq1rk1/1p2bppp/p1np1n2/4p3/4P3/1BN3B3/PPPQ1PPP/2KR1B1R b - - 0 1", "explanation": "Black sacrifices a Rook for a Knight or Bishop (a classic motif in the Sicilian Dragon is ...Rxc3) to permanently damage White's pawn structure and seize the dark squares."},
    "35. Positional piece sacrifice": {"fen": "r1bq1rk1/pp2nppp/2n1p3/3p4/1bB1P3/2N2N2/PB3PPP/R2QR1K1 w - - 0 1", "explanation": "A minor piece is sacrificed for massive, long-term positional compensation, such as an unbreakable blockade or a massive, rolling pawn center."},
    "36. Positional queen sacrifice": {"fen": "r1bq1rk1/pp2nppp/2n1p3/3p4/1bB1P3/2N2N2/PB3PPP/R2QR1K1 w - - 0 1", "explanation": "The rarest of sacrifices. The Queen is given up for two minor pieces or a Rook, not for a forced mate, but because the resulting position is strategically dominant and impenetrable."},
    "37. Penetration": {"fen": "6k1/1R3ppp/8/8/8/8/8/6K1 w - - 0 1", "explanation": "A heavy piece (like a Rook) infiltrates deep into enemy territory, usually reaching the 7th or 8th rank to terrorize pawns and trap the King."},
    "38. Activation of pieces": {"fen": "r1bq1rk1/ppp2ppp/2n2n2/3p4/1bB1P3/2N2N2/PB3PPP/R2QR1K1 w - - 0 1", "explanation": "The strategic maneuver of moving a poorly placed, passive piece to a central, active square where its scope and attacking potential are drastically increased."},
    "39. Intermediate move": {"fen": "3r2k1/p4ppp/1pn5/8/8/1B6/P4PPP/3R2K1 w - - 0 1", "explanation": "Also known as a 'Zwischenzug'. Instead of automatically recapturing a piece, a player inserts a surprising, forcing move (often a check) that changes the entire tactical calculation."},
    "40. Weakness of the isolated pawn": {"fen": "r1bq1rk1/ppp2ppp/2n5/3p4/3P4/3B1N2/PP1Q1PPP/R4RK1 b - - 0 1", "explanation": "An isolated pawn (here, Black's d5 pawn) cannot be defended by other pawns. It becomes a static target that White will blockade and repeatedly attack."},
    "41. Isolated pawn, attack": {"fen": "r1bq1rk1/pp2bppp/2n5/3p4/3P4/3B1N2/PP3PPP/R1BQR1K1 w - - 0 1", "explanation": "White has an Isolated Queen's Pawn (IQP) on d4. While it cannot be defended by other pawns, it provides massive space and open files, allowing White to launch a fierce Kingside attack."},
    "42. Isolated pawn, breakthrough by d5": {"fen": "r1bq1rk1/pp2bppp/2n5/3P4/8/3B1N2/PP3PPP/R1BQR1K1 b - - 0 1", "explanation": "The ultimate goal of the player with the IQP. By successfully pushing d4-d5 and sacrificing or trading the pawn, White forcefully blows open the center of the board to unleash their pieces."},
    "43. Hanging pawns": {"fen": "r1bq1rk1/pp3ppp/2n2n2/3p4/2PP4/5N2/P3BPPP/R1BQ1RK1 w - - 0 1", "explanation": "Pawns side-by-side on c4 and d4, separated from the rest of their pawn chain. Like the IQP, they offer dynamic attacking potential and space, but require constant, careful defense."},
    "44. Backward pawn": {"fen": "r1bq1rk1/pp2bppp/3p1n2/2p5/4P3/2N1B3/PPP2PPP/R2Q1RK1 w - - 0 1", "explanation": "Black's d6 pawn is 'backward'. It has been left behind by the c5 pawn and cannot be safely defended by another pawn. It sits on a semi-open file, making it a permanent, static target for White."},
    "45. Passed pawn": {"fen": "8/p5kp/1P6/8/8/8/P7/1K6 w - - 0 1", "explanation": "A pawn with no enemy pawns in front of it or on adjacent files to stop it. Here, White's b6 pawn is incredibly dangerous and is threatening to march to promotion."},
    "46. Phalanx": {"fen": "8/8/3k4/8/3PP3/8/3K4/8 w - - 0 1", "explanation": "A powerful formation where two or more pawns stand side-by-side on the same rank (here, d4 and e4). They control a massive wall of squares in front of them and prevent enemy pieces from advancing."},
    "47. Rook manoeuvre": {"fen": "r1bq1rk1/ppp2ppp/2n5/3p4/3P4/3B1N2/PP3PPP/R2QR1K1 w - - 0 1", "explanation": "Also known as a 'Rook Lift'. White's Rook on e1 is preparing to maneuver via the 3rd rank (Re3 to Rh3 or Rg3) to join a Kingside attack, bypassing its own pawns."},
    "48. Knight manoeuvre": {"fen": "r1bq1rk1/ppp1bppp/2n2n2/3p4/3P4/3B1N2/PPPN1PPP/R1BQR1K1 w - - 0 1", "explanation": "Knights are slow and require precise maneuvering. Here, White has placed a Knight on d2, preparing a classic re-routing journey to f1 and then to the aggressive g3 or e3 squares."},
    "49. Bishop manoeuvre": {"fen": "r1bq1rk1/2p1bppp/p1np1n2/1p2p3/4P3/1B3N2/PPPP1PPP/RNBQR1K1 w - - 0 1", "explanation": "Bishops often need to be repositioned to find better diagonals. In this classic Ruy Lopez setup, White's Bishop has maneuvered from f1 to b5, to a4, and finally to b3 to eye the f7 square."},
    "50. Queen manoeuvre": {"fen": "r1bq1rk1/ppp1bppp/2n2n2/3p4/3P4/3B1N2/PPP2PPP/R1BQ1RK1 w - - 0 1", "explanation": "The Queen is brought from its starting square to a more active, threatening post. Here, White is preparing Qd2 followed by Qh6, to directly challenge Black's King position."},
    "51. Capturing the queen": {"fen": "rn2k1nr/p1pp1ppp/b3p3/8/1p1PP3/2N2N2/PqPQ1PPP/R3KB1R w KQkq - 0 1", "explanation": "A classic trap. Black's Queen became too greedy and captured the 'poisoned' pawn on b2. White plays Rb1, and the Black Queen is completely trapped with no safe escape squares."},
    "52. Piece on a bad square": {"fen": "r1bq1rk1/ppp1bppp/3p1n2/4p3/N2PP3/5N2/PPP2PPP/R1BQR1K1 b - - 0 1", "explanation": "White's Knight on a4 is misplaced. It has no targets, controls no central squares, and is disconnected from the rest of the army. 'A Knight on the rim is dim.'"},
    "53. Knight on the edge of the board": {"fen": "r1bq1rk1/1pp1bppp/p1np1n2/4p3/N3P3/3P1N2/PPP1BPPP/R1BQ1RK1 b - - 0 1", "explanation": "Similar to the bad square theme, a Knight relegated to the edge (the a or h files) loses exactly half of its potential mobility, making it a severe positional liability."},
    "54. Knight on d6, e6 or d3, e3": {"fen": "r1bq1rk1/ppp1bppp/3N1n2/4p3/4P3/5N2/PPP2PPP/R1BQR1K1 b - - 0 1", "explanation": "An 'Octopus Knight'. White has managed to plant a Knight deep into Black's territory on d6. It cannot be chased away by pawns and severely cramps Black's entire position."},
    "55. Opposite coloured bishops": {"fen": "8/5k2/8/4b3/8/4B3/5K2/8 w - - 0 1", "explanation": "A famous drawing mechanism in endgames, but highly attacking in middlegames. Because the Bishops travel on different colored squares, they can never attack or block each other."},
    "56. Pair of bishops": {"fen": "8/5k2/8/4b1b1/8/4B1B1/5K2/8 w - - 0 1", "explanation": "Owning both the light and dark-squared Bishops (the 'Bishop Pair') is considered a tangible, long-term advantage, as they can sweep across the entire board without leaving any color weaknesses."},
    "57. Strong knight versus bad bishop": {"fen": "8/1p3k2/p1p5/P1P2N2/8/8/5K2/2b5 w - - 0 1", "explanation": "Black's Bishop is trapped by its own pawns on light squares, making it 'bad'. Meanwhile, White's Knight is perfectly centralized and dominates the board, creating a winning advantage."},
    "58. Exchange of a piece": {"fen": "r1bq1rk1/ppp1bppp/2n2n2/3p2B1/3P4/2N2N2/PPP1BPPP/R2Q1RK1 w - - 0 1", "explanation": "Exchanging is not just trading; it is a tactical decision. Here, White is preparing to play Bxf6, intentionally trading a Bishop for a Knight to remove Black's best defender of the d5 square."},
    "59. Avoiding exchanges": {"fen": "r1bq1rk1/ppp1bppp/2n2n2/3p2B1/3P4/2NB1N2/PPP2PPP/R2Q1RK1 w - - 0 1", "explanation": "When you have a space advantage or a fierce attack, trading pieces helps the defender. Here, if Black offers a trade, White will actively retreat to keep tension on the board."},
    "60. Liquidation": {"fen": "6k1/5ppp/8/8/4Q3/8/1B3PPP/3q2K1 w - - 0 1", "explanation": "White is up a piece (the Bishop on b2) but Black's Queen is aggressively attacking. White plays Qxd1, trading Queens to 'liquidate' all danger and transition into an easily won endgame."},
    "61. Advantage in the centre": {"fen": "r1bq1rk1/ppp1bppp/2n2n2/3p4/3P4/2PB1N2/PP3PPP/RNBQ1RK1 w - - 0 1", "explanation": "White has classical central control. The d4 pawn is firmly supported, and White's pieces are perfectly mobilized behind this central space advantage, restricting Black's maneuverability."},
    "62. Breakthrough in the centre": {"fen": "r1bq1rk1/pp2bppp/2n2n2/2pP4/8/2NB1N2/PP3PPP/R1BQR1K1 b - - 0 1", "explanation": "White has just played the central breakthrough d4-d5! This explosive pawn push breaks the tension, opening files for the Rooks and diagonals for the Bishops."},
    "63. Blowing up the centre": {"fen": "r1bq1rk1/pp1nbppp/2p1pn2/3p4/2PP4/2N2NP1/PP2PPBP/R1BQ1RK1 w - - 0 1", "explanation": "When the opponent's King is trapped in the middle, or your pieces are better developed, 'blowing up the center' involves sacrificing pawns (like e4 or c4 pushes) to violently open the central files."},
    "64. Hedgehog": {"fen": "rn1q1rk1/pb2bppp/1p1ppn2/8/2P1P3/2N2NP1/PP3PBP/R1BQ1RK1 b - - 0 1", "explanation": "A famous defensive setup. Black places pawns on a6, b6, d6, and e6. Like a hedgehog rolling into a spiky ball, it is incredibly difficult for White to attack without getting pricked."},
    "65. Hedgehog, blowing up with d5": {"fen": "rn1q1rk1/pb2bppp/1p2pn2/3p4/2P1P3/2N2NP1/PP3PBP/R1BQ1RK1 w - - 0 1", "explanation": "The Hedgehog is not purely defensive. Black waits patiently for the perfect moment to strike back in the center with a well-timed ...d5! or ...b5!, instantly springing the position open."},
    "66. Minority attack": {"fen": "r1q2rk1/pp1n1ppp/2pbpn2/3p4/1PPP4/P1N1P3/3BBPPP/R2Q1RK1 w - - 0 1", "explanation": "In the Carlsbad structure, White launches a 'Minority Attack' by pushing the a and b pawns (a minority of 2 pawns) against Black's queenside majority (3 pawns) to create a permanent weakness on c6."},
    "67. Stone wall": {"fen": "rnbq1rk1/ppp1b1pp/4pn2/3p1p2/2PP4/5NP1/PP2PPBP/RNBQ1RK1 w - - 0 1", "explanation": "Black has established the Dutch Stonewall setup with pawns on f5, e6, d5, and c6. It creates an iron grip on the e4 square, though it permanently weakens the e5 square."},
    "68. King's Indian attack against the white king": {"fen": "r1bq1rk1/ppp3b1/3p2np/3Ppp2/2P5/2N3P1/PP2NPBP/R2Q1RK1 b - - 0 1", "explanation": "In the King's Indian Defense, Black locks the center and launches a terrifying pawn storm (...f5, ...f4, ...g5) directly at the White King."},
    "69. Sicilian piece sacrifice on d5": {"fen": "r1bqkb1r/1p3ppp/p1np1n2/3Np3/4P3/1N2B3/PPP2PPP/R2QKB1R b KQkq - 0 1", "explanation": "A thematic Sicilian motif. White often sacrifices a Knight on d5 to permanently eliminate Black's central control and rip open the e-file against the uncastled Black King."},
    "70. Sicilian exchange sacrifice on c3": {"fen": "r1bq1rk1/1p2bppp/p2p1n2/4p3/4P3/1PN1B3/1PP2PPP/R2Q1RK1 b - - 0 1", "explanation": "One of Black's most powerful weapons in the Sicilian. Black plays ...Rxc3!, sacrificing the exchange to shatter White's queenside pawn structure and destroy the defender of the e4 pawn."},
    "71. Other Sicilian piece sacrifices": {"fen": "r1bqkb1r/1p1n1ppp/p2p1n2/4p3/3NPP2/2N1B3/PPP3PP/R2QKB1R w KQkq - 0 1", "explanation": "The Sicilian is highly tactical. White frequently looks for sacrifices on b5, e6, or f5 to disrupt Black's development before Black can find safety."},
    "72. Blockade": {"fen": "r1bq1rk1/pp3ppp/2n5/2bp4/3N4/2PB4/PP3PPP/R1BQR1K1 b - - 0 1", "explanation": "A fundamental concept pioneered by Nimzowitsch. White's Knight on d4 is the perfect blockader. It stops the passed d5 pawn from advancing while safely attacking other squares."},
    "73. Weak square": {"fen": "r1bq1rk1/pp3ppp/2n5/3p4/3N4/2P1B3/PP3PPP/R2Q1RK1 w - - 0 1", "explanation": "A square that can no longer be defended by a pawn. In many structures, the d5 square becomes a permanent 'hole' where White can safely plant an unassailable Knight."},
    "74. Perpetual check": {"fen": "7k/7p/8/8/8/8/1q4PK/6R1 b - - 0 1", "explanation": "A saving mechanism in lost positions. The weaker side forces a draw by delivering an endless, unbreakable series of checks that the opponent's King cannot escape."},
    "75. Profilax": {"fen": "r1bq1rk1/ppp1bppp/2n2n2/3p4/3P4/2PB1N1P/PP3PP1/RNBQR1K1 b - - 0 1", "explanation": "Prophylaxis. White plays h3. This seemingly quiet move prevents Black from ever playing ...Bg4 or ...Ng4, proactively stopping the opponent's plan before it even starts."},
    "76. Space advantage": {"fen": "r1bq1rk1/ppp1bppp/2n2n2/3pP3/3P4/2PB1N2/PP3PPP/RNBQK2R b KQkq - 0 1", "explanation": "By pushing pawns deep into enemy territory (like the e5 pawn), a player gains a 'Space Advantage.' Their pieces have plenty of room to maneuver, while the opponent is cramped and restricted."},
    "77. Double rook sacrifice": {"fen": "r3k2r/ppp2ppp/2n5/2b1p3/2B1P1n1/2NP4/PPP3PP/R1BQK2R w KQkq - 1 9", "explanation": "A spectacular, rare tactical motif (famous from the 'Immortal Game'). A player intentionally leaves both of their rooks hanging in the corners to lure the opponent's Queen away from defending the King."}
}

# --- NEW: Theoretical Endgame Reference Dictionary ---
ENDGAME_THEMES = {
    "1. The Lucena Position": {"fen": "1K6/1P6/8/8/8/8/r7/2R2k2 w - - 0 1", "explanation": "The most important rook endgame. White's King is sheltering in front of its pawn on the 8th rank. White wins by using the Rook to cut off the Black King and then 'building a bridge' (Rd4) to shield their King from checks."},
    "2. The Philidor Position": {"fen": "2k5/7R/r7/3K4/3P4/8/8/8 b - - 0 1", "explanation": "The quintessential drawing technique in rook endgames. Black keeps their King on the promotion square and leaves their Rook on the 3rd rank (the 6th rank from White's perspective) to prevent the White King from advancing."},
    "3. The Vancura Position": {"fen": "8/8/8/8/8/7R/p5K1/1k6 w - - 0 1", "explanation": "A famous drawing method against a rook pawn. The weaker side places their Rook behind the pawn on the side (on the 3rd rank) to deliver endless lateral checks once the attacking King tries to support the pawn."},
    "4. The Tarrasch Rule": {"fen": "8/P7/8/8/8/8/6k1/R7 w - - 0 1", "explanation": "Dr. Siegbert Tarrasch formulated this golden rule: 'Always put the rook behind the passed pawn.' Here, the White Rook supports the pawn's advance from behind, maximizing both the pawn's safety and the Rook's mobility."},
    "5. The Square of the Pawn": {"fen": "8/8/8/p7/8/8/8/7K w - - 0 1", "explanation": "A mental shortcut to calculate if a King can catch a runaway pawn without calculating every move. Draw an imaginary square from the pawn to the promotion rank. If the defending King can step into this square, it catches the pawn."},
    "6. Direct Opposition": {"fen": "8/8/8/8/4k3/8/4K3/8 w - - 0 1", "explanation": "The Kings face each other with one square between them. Whoever has to move 'loses' the opposition and must give way, allowing the enemy King to penetrate."},
    "7. Distant Opposition": {"fen": "8/8/4k3/8/8/8/4K3/8 w - - 0 1", "explanation": "The Kings face each other with an odd number of squares (usually 3 or 5) between them. The goal is to maneuver this into Direct Opposition to force the opponent's King backward."},
    "8. Triangulation": {"fen": "8/8/8/4k3/8/4K3/4P3/8 w - - 0 1", "explanation": "A technique where a King moves in a triangle over three squares to return to the exact same position, but passing the turn to the opponent to force them into Zugzwang."},
    "9. The Trebuchet (Mutual Zugzwang)": {"fen": "8/8/8/3k4/4p3/4P3/3K4/8 w - - 0 1", "explanation": "A fascinating pawn endgame where whoever's turn it is to move loses! Both Kings are tied to defending their own pawn and attacking the opponent's. Moving abandons the defense."},
    "10. The Wrong-Colored Bishop": {"fen": "8/8/8/8/8/4b1k1/7p/7K w - - 0 1", "explanation": "A tragic draw for the stronger side. Even though Black is up a Bishop and a passed pawn, the Bishop controls the dark squares, but the promotion square (h1) is a light square. The White King can never be forced out of the corner."},
    "11. Key Squares": {"fen": "8/8/8/4k3/3P4/8/4K3/8 b - - 0 1", "explanation": "In King and Pawn endgames, if the attacking King can occupy the 'Key Squares' directly in front of their passed pawn, the pawn will promote by force, regardless of who has the opposition."},
    "12. Centurini's Rule": {"fen": "8/8/8/4B3/8/8/p5k1/K7 w - - 0 1", "explanation": "In Bishop vs. Pawn endings, if the defending King can reach the square in front of the pawn (and isn't chased away), or if the defending Bishop can permanently control the promotion square, it is a draw."},
    "13. The Saavedra Position": {"fen": "8/2P5/8/5k2/8/8/1r6/K7 w - - 0 1", "explanation": "One of the most famous endgame studies ever. White is trying to promote. Promoting to a Queen leads to a draw by stalemate or a skewer, but underpromoting to a Rook wins the game!"},
    "14. Réti's Maneuver": {"fen": "7K/8/k1P5/7p/8/8/8/8 w - - 0 1", "explanation": "A miraculous draw. The White King seems too far away to stop the Black pawn and too far away to support its own pawn. But by moving diagonally, the King creates a dual threat and saves the game."},
    "15. Queen vs. Pawn on the 7th": {"fen": "8/2P5/8/8/8/3k4/8/1Q4K1 b - - 0 1", "explanation": "Normally, a Queen easily defeats a lone pawn. The winning technique involves delivering checks and pins to force the enemy King to step in front of its own pawn, giving the attacker time to bring their own King closer."},
    "16. Queen vs. Rook Pawn Draw": {"fen": "8/p7/1K6/8/8/8/8/6kq w - - 0 1", "explanation": "The major exception to the Queen vs. Pawn rule. If the defending side has a Rook pawn (a or h file) or Bishop pawn (c or f file) on the 7th rank, forcing the King in front of the pawn leads to an automatic stalemate."},
    "17. Philidor's Queen vs Rook": {"fen": "8/8/8/8/3k4/8/3P4/1R2K2q w - - 0 1", "explanation": "The Queen eventually wins against a lone Rook, but it requires precision. The goal is to force the King and Rook apart, then use double attacks (forks) with the Queen to win the Rook."},
    "18. Bishop and Knight Mate": {"fen": "8/8/8/8/8/3K4/2B5/k1N5 w - - 0 1", "explanation": "One of the most difficult fundamental checkmates. The defender's King must be methodically driven into a corner of the board that matches the color of the attacker's Bishop."},
    "19. Troitzky Line": {"fen": "8/8/8/8/8/4NN2/7p/5K1k w - - 0 1", "explanation": "Two Knights cannot force checkmate against a lone King. However, if the defender has a pawn that is safely blocked behind the 'Troitzky Line,' the attacker can construct a mating net because the pawn prevents stalemate."},
    "20. Frontal Defense": {"fen": "8/8/8/8/3k4/8/3P4/2R1K3 b - - 0 1", "explanation": "When defending a pawn endgame with a Rook, sometimes the best defense is to attack the passed pawn directly from the front, minimizing the mobility of the attacking Rook."}
}

# --- 2. Data Loading & Helper Functions ---
# NEW: Lichess Tablebase API call function
def query_lichess_tablebase(fen):
    url = f"https://tablebase.lichess.ovh/standard?fen={fen}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API returned status code {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

@st.cache_data
def load_data(db_path):
    if not os.path.exists(db_path):
        st.error(f"Database not found at: {db_path}")
        return pd.DataFrame()

    conn = sqlite3.connect(db_path)
    
    # Check if tablebase columns exist
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(moves)")
    m_columns = [col[1] for col in cursor.fetchall()]
    tb_wdl_sql = "m.tb_wdl," if "tb_wdl" in m_columns else "NULL AS tb_wdl,"
    tb_dtz_sql = "m.tb_dtz," if "tb_dtz" in m_columns else "NULL AS tb_dtz,"

    # Check if pawn_structure exists safely
    cursor.execute("PRAGMA table_info(games)")
    g_columns = [col[1] for col in cursor.fetchall()]
    ps_sql = "g.pawn_structure," if "pawn_structure" in g_columns else "NULL AS pawn_structure,"

    query = f"""
        SELECT
            g.id AS game_id, g.eco_code, g.opening_name, g.white_player, g.black_player,
            g.white_elo, g.black_elo, g.result, g.game_category, g.swings, {ps_sql}
            g.w_blunders, g.b_blunders, g.w_missed_wins, g.b_missed_wins,
            g.w_mistakes, g.b_mistakes, g.w_inaccuracies, g.b_inaccuracies,
            g.w_best_moves, g.b_best_moves,
            m.id AS move_id, m.move_number, m.color, m.notation, m.engine_eval, m.cp_loss, m.wev,
            m.fen, m.annotation, m.piece_count, {tb_wdl_sql} {tb_dtz_sql} m.is_blunder, round, board, video_url
        FROM games g
        JOIN moves m ON g.id = m.game_id
        ORDER BY g.id ASC, m.id ASC
    """

    try:
        df = pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Database Error: {e}")
        df = pd.DataFrame() 
    finally:
        conn.close()
    return df

def find_exact_image(graphs_dir, game_id):
    if not os.path.exists(graphs_dir): return None
    target = f"Game_{str(game_id).zfill(3)}_Swing.png"
    path = os.path.join(graphs_dir, target)
    if os.path.exists(path): return path
    try:
        for f in os.listdir(graphs_dir):
            if f.lower() == target.lower():
                return os.path.join(graphs_dir, f)
    except Exception:
        pass
    return None

def clean_annotation(note):
    if not isinstance(note, str) or note.strip() == "": return ""
    def eval_repl(match):
        cp = int(match.group(1))
        eval_val = cp / 100.0
        if eval_val > 0: return f"(Engine favors White: +{eval_val:.2f})"
        elif eval_val < 0: return f"(Engine favors Black: {eval_val:.2f})"
        else: return "(Position is equal: 0.00)"
    note = re.sub(r'\[%eval (-?\d+)(?:,\d+)?\]', eval_repl, note)
    def cal_repl(match):
        arrows = match.group(1).split(',')
        translations = []
        for arrow in arrows:
            if len(arrow) >= 5:
                color = arrow[0].upper()
                start, end = arrow[1:3], arrow[3:5]
                if color == 'R': translations.append(f"Threat: {start} to {end}")
                elif color == 'G': translations.append(f"Good move: {start} to {end}")
                elif color in ['O', 'Y']: translations.append(f"Idea: {start} to {end}")
                else: translations.append(f"Look at {start} to {end}")
        return "(Arrows: " + ", ".join(translations) + ")"
    note = re.sub(r'\[%cal (.*?)\]', cal_repl, note)
    def tqu_repl(match):
        moves = re.findall(r'"([a-h][1-8][a-h][1-8])"', match.group(0))
        if moves: return f"🧠 Quiz: Can you find the best move? (Hint: look at {moves[0]})"
        return "🧠 Quiz: What would you play here?"
    note = re.sub(r'\[%tqu .*?\]', tqu_repl, note)
    note = re.sub(r'\[%mdl \d+\]', '💡 Theme:', note)
    note = note.replace('[#]', '🎯 Critical Position / Checkmate Threat')
    return re.sub(r'\s+', ' ', note).strip()

def jump_to_move(move_num):
    st.session_state.scrubber = move_num

def main():
    # 1. SIDEBAR DATABASE SELECTION (This must happen first!)
    available_dbs = get_database_files()
    
    # THE FIX: Safely find the list position (index) of the database passed by your Launcher
    try:
        default_index = available_dbs.index(st.session_state.active_db)
    except ValueError:
        default_index = 0 # Fallback to 0 if the launcher passed a misspelled or missing file
        
    # Tell the dropdown menu to open to that specific index!
    selected_db_file = st.sidebar.selectbox("Select Database File:", available_dbs, index=default_index)
    
    # Sync the memory back up in case the user manually changes the dropdown
    st.session_state.active_db = selected_db_file
    
    db_path = f"databases/{selected_db_file}"
    st.sidebar.markdown("---")

    
    # 2. SET UP DIRECTORIES BASED ON YOUR SELECTION
    db_name_only = os.path.splitext(os.path.basename(db_path))[0]
    graphs_dir = f"data/graphs_{db_name_only}"    
    
    # 3. LOAD THE DATA
    df = load_data(db_path)

    if df.empty:
        st.warning("Dashboard waiting for data. Please check your database.")
        return
        
    if 'game_category' in df.columns: df['game_category'] = df['game_category'].fillna('Uncategorized')
    if 'swings' in df.columns: df['swings'] = pd.to_numeric(df['swings'], errors='coerce').fillna(0).astype(int)

    total_games = df['game_id'].nunique()

    # --- Initialize Session States ---
    if 'analyzed_game_id' not in st.session_state: st.session_state.analyzed_game_id = None
    if 'scroll_target' not in st.session_state: st.session_state.scroll_target = None 

    cols_to_fix = [
        'cp_loss', 'wev', 'white_elo', 'black_elo', 
        'w_blunders', 'b_blunders', 'w_missed_wins', 'b_missed_wins',
        'w_mistakes', 'b_mistakes', 'w_inaccuracies', 'b_inaccuracies',
        'w_best_moves', 'b_best_moves', 'piece_count', 'tb_wdl', 'tb_dtz'
    ]
    for col in cols_to_fix:
        if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df['total_blunders'] = df['w_blunders'] + df['b_blunders']
    df['total_missed_wins'] = df['w_missed_wins'] + df['b_missed_wins']
    if 'w_mistakes' in df.columns:
        df['total_sloppiness'] = df['w_mistakes'] + df['b_mistakes'] + df['w_inaccuracies'] + df['b_inaccuracies']
        df['total_best_moves'] = df['w_best_moves'] + df['b_best_moves']

    df['annotation'] = df['annotation'].apply(clean_annotation)

    # --- 4. Sidebar Controls & Logic ---
    st.sidebar.header("Educational Filters")

    if st.sidebar.button("🔄 Reset All Filters", width='stretch'):
        st.session_state.eco_key, st.session_state.opening_key = [], []
        st.session_state.category_key, st.session_state.tag_key = [], []
        
        # NEW: Wipe the slider memory!
        if 'blunder_key' in st.session_state: del st.session_state['blunder_key']
        if 'sloppy_key' in st.session_state: del st.session_state['sloppy_key']

        st.session_state.structure_key = []
        st.session_state.search_key = ""
        st.session_state.missed_win_key, st.session_state.best_move_key = False, False
        st.session_state.endgame_key = "Show All Games"
        st.session_state.w_elo_key = (int(df['white_elo'].min()), int(df['white_elo'].max() + 1))
        st.session_state.b_elo_key = (int(df['black_elo'].min()), int(df['black_elo'].max() + 1))
        st.session_state.wev_key = (float(df['wev'].min()), float(df['wev'].max()))
        st.session_state['blunder_key'] = (0, 15)
        if 'swings' in df.columns: st.session_state.swings_key = (int(df['swings'].min()), int(df['swings'].max()))
        if 'total_sloppiness' in df.columns: 
            st.session_state.sloppy_key = (0, int(df['total_sloppiness'].max()))
        st.session_state.analyzed_game_id = None
        st.session_state.scroll_target = 'gallery-top'
        st.rerun()


        st.sidebar.markdown("---")
        st.sidebar.subheader("Game Dynamics")

    if 'pawn_structure' in df.columns:
        valid_structures = sorted([s for s in df['pawn_structure'].unique() if pd.notna(s) and s != "Unclassified / Flexible"])
        if valid_structures:
            selected_structures = st.sidebar.multiselect("🧱 Filter by Pawn Structure", valid_structures, key='structure_key')
        else: selected_structures = []
    else: selected_structures = []

    if 'game_category' in df.columns:
        selected_categories = st.sidebar.multiselect("Filter by Game Dynamics", sorted(df['game_category'].unique().tolist()), key='category_key')
    else: selected_categories = []

    if 'swings' in df.columns:
        min_swings_val, max_swings_val = int(df['swings'].min()), int(df['swings'].max())
        if min_swings_val == max_swings_val: max_swings_val += 1
        swings_range = st.sidebar.slider("Min/Max Swings", min_swings_val, max_swings_val, (min_swings_val, max_swings_val), key='swings_key')
    else: swings_range = (0, 100)


    # UPDATED: Expanded Radio Button for Endgames
    endgame_filter = st.sidebar.radio(
        "♟️ Endgame Filter", 
        [
            "Show All Games", 
            "Only ≤ 7-Piece Endgames", 
            "Only ≤ 6-Piece Endgames",
            "Only ≤ 5-Piece Endgames",
            "Only ≤ 4-Piece Endgames",
            "Only 3-Piece Endgames"
        ], 
        key='endgame_key'
    )

    st.sidebar.markdown("---")
    all_ecos = sorted(df['eco_code'].dropna().unique().tolist())
    selected_ecos = st.sidebar.multiselect("Filter by ECO Code", all_ecos, key='eco_key')
    all_openings = sorted(df['opening_name'].dropna().unique().tolist())
    selected_openings = st.sidebar.multiselect("Filter by Opening Name", all_openings, key='opening_key')

    st.sidebar.markdown("---")
    min_w_elo, max_w_elo = int(df['white_elo'].min()), int(df['white_elo'].max())
    white_elo_range = st.sidebar.slider("White Elo Range", min_w_elo, max_w_elo + 1, (min_w_elo, max_w_elo + 1), 10, key='w_elo_key')
    min_b_elo, max_b_elo = int(df['black_elo'].min()), int(df['black_elo'].max())
    black_elo_range = st.sidebar.slider("Black Elo Range", min_b_elo, max_b_elo + 1, (min_b_elo, max_b_elo + 1), 10, key='b_elo_key')

    st.sidebar.markdown("---")
    st.sidebar.subheader("Move Quality Filters")
    
# 1. Calculate the maximums safely, defaulting to 0 if something is weird
    max_blunders = int(df['total_blunders'].max()) if pd.notna(df['total_blunders'].max()) else 0
    max_sloppy_val = int(df['total_sloppiness'].max()) if pd.notna(df['total_sloppiness'].max()) else 0

# 2. --- BLUNDER SLIDER ---
    if max_blunders > 0:
        # 1. Initialize or clamp the memory FIRST
        if 'blunder_key' not in st.session_state:
            st.session_state.blunder_key = (0, max_blunders)
        else:
            saved_min, saved_max = st.session_state.blunder_key
            st.session_state.blunder_key = (min(saved_min, max_blunders), min(saved_max, max_blunders))

        # 2. Draw the slider WITHOUT the default value argument
        blunder_range = st.sidebar.slider("Blunders", 0, max_blunders, key='blunder_key')
    else:
        st.sidebar.success("🎯 Perfect play! No blunders found.")
        blunder_range = (0, 0)    
    
# 3. --- SLOPPINESS SLIDER ---
    if max_sloppy_val > 0:
        # 1. Initialize or clamp the memory FIRST
        if 'sloppy_key' not in st.session_state:
            st.session_state.sloppy_key = (0, max_sloppy_val)
        else:
            saved_min, saved_max = st.session_state.sloppy_key
            st.session_state.sloppy_key = (min(saved_min, max_sloppy_val), min(saved_max, max_sloppy_val))

        # 2. Draw the slider WITHOUT the default value argument
        sloppy_range = st.sidebar.slider("Mistakes & Inaccuracies", 0, max_sloppy_val, key='sloppy_key')
    else:
        st.sidebar.success("🤯 Perfect play! No mistakes or inaccuracies found.")
        sloppy_range = (0, 0)
        
    require_missed_wins = st.sidebar.checkbox("Only Show Missed Wins", key='missed_win_key')
    if 'total_best_moves' in df.columns:
        require_best_moves = st.sidebar.checkbox("🌟 Only Show Games with Best/Strong Moves", key='best_move_key')
    else: 
        require_best_moves = False
        
# 1. Calculate min and max safely from the dataframe
    min_wev = float(df['wev'].min()) if pd.notna(df['wev'].min()) else 0.0
    max_wev = float(df['wev'].max()) if pd.notna(df['wev'].max()) else 0.0

    # 2. --- WEV SLIDER ---
    if min_wev < max_wev:
        wev_range = st.sidebar.slider("WEV (Win Expectancy Value) Range", min_wev, max_wev, (min_wev, max_wev), 0.01, key='wev_key')
    else:
        # If they are exactly the same, skip the slider so Streamlit doesn't crash
        st.sidebar.info(f"ℹ️ Engine data missing: WEV is flat at {min_wev}")
        wev_range = (min_wev, max_wev)
        
    st.sidebar.markdown("---")
    st.sidebar.subheader("Coach's Insights")
    tag_options = {"⚠️ Critical Blunder": "⚠️", "🎯 Checkmate Threat": "🎯", "🧠 Engine Quiz": "🧠", "💡 Tactical Theme": "💡", "🎓 Coach Summary": "🎓"}
    selected_tags = st.sidebar.multiselect("Quick Tag Filters", list(tag_options.keys()), key='tag_key')
    search_notes = st.sidebar.text_input("🔍 Or search specific words (e.g., 'Pin', 'Fork')", key='search_key')



    # Applying Global Filters
    filtered_df = df.copy()

   # 1. Default this to False so Python always knows it exists!
    require_video = False 

    # 2. VIDEO OPTIONS (Only show if the current database supports it!)
    if 'video_url' in df.columns:
        st.sidebar.markdown("---")
        st.sidebar.subheader("Video Options")
        require_video = st.sidebar.checkbox("🎬 Games with idChess video")

    # 3. Filter only if the box exists AND is checked
    if require_video:
        filtered_df = filtered_df[filtered_df['video_url'].notna() & (filtered_df['video_url'].astype(str).str.strip() != '')]         
    
    if selected_categories: filtered_df = filtered_df[filtered_df['game_category'].isin(selected_categories)]
    if selected_structures: filtered_df = filtered_df[filtered_df['pawn_structure'].isin(selected_structures)]
    if 'swings' in df.columns: filtered_df = filtered_df[(filtered_df['swings'] >= swings_range[0]) & (filtered_df['swings'] <= swings_range[1])]
    if selected_ecos: filtered_df = filtered_df[filtered_df['eco_code'].isin(selected_ecos)]
    if selected_openings: filtered_df = filtered_df[filtered_df['opening_name'].isin(selected_openings)]

    # UPDATED: Expanded endgame filter logic
    if endgame_filter == "Only ≤ 7-Piece Endgames" and 'piece_count' in df.columns:
        valid_endgame_games = df[df['piece_count'] <= 7]['game_id'].unique()
        filtered_df = filtered_df[filtered_df['game_id'].isin(valid_endgame_games)]
    elif endgame_filter == "Only ≤ 6-Piece Endgames" and 'piece_count' in df.columns:
        valid_endgame_games = df[df['piece_count'] <= 6]['game_id'].unique()
        filtered_df = filtered_df[filtered_df['game_id'].isin(valid_endgame_games)]
    elif endgame_filter == "Only ≤ 5-Piece Endgames" and 'piece_count' in df.columns:
        valid_endgame_games = df[df['piece_count'] <= 5]['game_id'].unique()
        filtered_df = filtered_df[filtered_df['game_id'].isin(valid_endgame_games)]
    elif endgame_filter == "Only ≤ 4-Piece Endgames" and 'piece_count' in df.columns:
        valid_endgame_games = df[df['piece_count'] <= 4]['game_id'].unique()
        filtered_df = filtered_df[filtered_df['game_id'].isin(valid_endgame_games)]
    elif endgame_filter == "Only 3-Piece Endgames" and 'piece_count' in df.columns:
        valid_endgame_games = df[df['piece_count'] <= 3]['game_id'].unique()
        filtered_df = filtered_df[filtered_df['game_id'].isin(valid_endgame_games)]

    filtered_df = filtered_df[
        (filtered_df['white_elo'] >= white_elo_range[0]) & (filtered_df['white_elo'] <= white_elo_range[1]) &
        (filtered_df['black_elo'] >= black_elo_range[0]) & (filtered_df['black_elo'] <= black_elo_range[1]) &
        (filtered_df['total_blunders'] >= blunder_range[0]) & (filtered_df['total_blunders'] <= blunder_range[1])
    ]
    
    if 'total_sloppiness' in df.columns: 
        filtered_df = filtered_df[
            (filtered_df['total_sloppiness'] >= sloppy_range[0]) & 
            (filtered_df['total_sloppiness'] <= sloppy_range[1])
]
    
    if require_missed_wins: 
        filtered_df = filtered_df[filtered_df['total_missed_wins'] > 0]
    if require_best_moves and 'total_best_moves' in df.columns: filtered_df = filtered_df[filtered_df['total_best_moves'] > 0]

    valid_wev_games = df[(df['wev'] >= wev_range[0]) & (df['wev'] <= wev_range[1])]['game_id'].unique()
    filtered_df = filtered_df[filtered_df['game_id'].isin(valid_wev_games)]

    if selected_tags:
        for tag_label in selected_tags:
            matching_games = filtered_df[filtered_df['annotation'].str.contains(tag_options[tag_label], na=False)]['game_id'].unique()
            filtered_df = filtered_df[filtered_df['game_id'].isin(matching_games)]

    if search_notes:
        matching_games = filtered_df[filtered_df['annotation'].str.contains(search_notes, case=False, na=False)]['game_id'].unique()
        filtered_df = filtered_df[filtered_df['game_id'].isin(matching_games)]

    available_games = filtered_df['game_id'].unique().tolist()
    filtered_count = len(available_games)

    # ==========================================
    # --- UI TABS ---
    # ==========================================
    tab1, tab2, tab3 = st.tabs(["♟️ Game Viewer", "📚 Study Room", "🏁 Endgame Encyclopedia"])

    # --- TAB 1: THE EXISTING DATABASE & GALLERY ---
    with tab1:
        # Overviews Section (Blunders & Openings)
        st.markdown("---")
        st.subheader("Database Overviews")
        
        if 'show_blunders' not in st.session_state: st.session_state.show_blunders = False
        if 'show_openings' not in st.session_state: st.session_state.show_openings = False
        
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            b_label = "📊 Hide Frequency of Blunders" if st.session_state.show_blunders else "📊 Show Frequency of Blunders"
            if st.button(b_label):
                st.session_state.show_blunders = not st.session_state.show_blunders
                st.rerun()

            if st.session_state.show_blunders:
                file_path = f"data/Blunder_Lessons_Per_Game_{db_name_only}.txt"
                try:
                    with open(file_path, "r", encoding="utf-8") as f: content = f.read()
                    search_phrase = "FREQUENCY OF BLUNDER COUNTS"
                    if search_phrase in content:
                        freq_section = content.split(search_phrase)[1].strip()
                        st.markdown("**Frequency of Blunder Counts**")
                        st.code(freq_section, language="text")
                    else:
                        st.markdown("**Frequency of Blunder Counts**")
                        st.code(content, language="text")
                except FileNotFoundError:
                    st.error(f"Could not find '{os.path.basename(file_path)}'.")

        with col_btn2:
            o_label = "📖 Hide Openings Summary" if st.session_state.show_openings else "📖 Show Openings Summary"
            if st.button(o_label):
                st.session_state.show_openings = not st.session_state.show_openings
                st.rerun()

            if st.session_state.show_openings:
                openings_path = f"data/Openings_Summary_{db_name_only}.txt"
                try:
                    with open(openings_path, "r", encoding="utf-8") as f: openings_content = f.read()
                    st.markdown("**Chess Openings Summary Report**")
                    st.code(openings_content, language="text")
                except FileNotFoundError:
                    st.error(f"Could not find '{os.path.basename(openings_path)}'.")

# THE GALLERY VIEW
        st.markdown("<div id='gallery-top'></div>", unsafe_allow_html=True) 
        
        # NEW: Load the synopses using the exact Active Session database!
        game_synopses_dict = load_synopses_dict(os.path.basename(db_path))
        
        header_col1, header_col2 = st.columns([3, 1])
        with header_col1:
            st.title("♟️ Chess Learning Lab Gallery")
            st.write(f"Active Session: `{os.path.basename(db_path)}`")
        with header_col2:
            st.metric(label="Games Matching Filters", value=f"{filtered_count} / {total_games}")
            
        st.markdown("---")
        
        if available_games:
            cols = st.columns(3)
            for idx, g_id in enumerate(available_games):
                col = cols[idx % 3]
                game_meta = filtered_df[filtered_df['game_id'] == g_id].iloc[0]
                with col:
                    st.subheader(f"Game {g_id}")
                    
                    # Dynamic Tags
                    tags = []
                    if 'game_category' in game_meta and pd.notna(game_meta['game_category']): tags.append(f"📈 {game_meta['game_category']}")
                    if 'pawn_structure' in game_meta and pd.notna(game_meta['pawn_structure']) and game_meta['pawn_structure'] != "Unclassified / Flexible": 
                        tags.append(f"🧱 {game_meta['pawn_structure']}")
                    if tags: st.caption(" | ".join(tags))
                    
                    st.write(f"**{game_meta['opening_name']}** ({game_meta['eco_code']})")
                    st.write(f"{game_meta['white_player']} vs {game_meta['black_player']}")
                    
                    img_path = find_exact_image(graphs_dir, g_id)
                    
                    if img_path: st.image(img_path, width='stretch') 
                    else: st.caption(f"(Graph missing: {graphs_dir}\\Game_{str(g_id).zfill(3)}_Swing.png)")

# Create columns for the side-by-side buttons
                    btn_col1, btn_col2 = st.columns(2)
                    
                    with btn_col1:
                        if st.button(f"Analyze Game {g_id}", key=f"btn_{g_id}", width='stretch', type='primary'):
                            st.session_state.analyzed_game_id = g_id
                            st.session_state.scroll_target = 'analysis-section'
                            if 'scrubber' in st.session_state: del st.session_state['scrubber']
                            st.rerun()
                            
                    with btn_col2:
                        # 1. Create a unique memory switch for this specific game
                        state_key = f"show_synopsis_{g_id}"
                        if state_key not in st.session_state:
                            st.session_state[state_key] = False
                            
                        # 2. Set the button text dynamically based on the switch
                        button_text = f"Close Game {g_id} Synopsis" if st.session_state[state_key] else f"Game {g_id} Synopsis"
                        
                        # 3. The Button: When clicked, flip the switch and rerun to update the screen
                        if st.button(button_text, key=f"synopsis_{g_id}", width='stretch', type='primary'):
                            st.session_state[state_key] = not st.session_state[state_key]
                            st.rerun()
                            
                        # 4. BACK IN THE COLUMN: Let's see exactly what the computer sees!
                        if st.session_state[state_key]:
                            
                            if str(g_id) in game_synopses_dict:
                                game_info = game_synopses_dict[str(g_id)]
                                st.warning(f"**Critical Mistakes:** {game_info['blunders']}\n\n**Synopsis:** {game_info['synopsis']}")
                            else:
                                st.error(f"Game {g_id} is NOT in the dictionary!")
            else:
                st.info("No games match the current filters.")

        # THE ANALYSIS SECTION (Deep Dive)
        if st.session_state.analyzed_game_id:
            st.markdown("---")
            st.markdown("<div id='analysis-section'></div>", unsafe_allow_html=True) 

            g_id = st.session_state.analyzed_game_id
            target_game = df[df['game_id'] == g_id].copy()
            meta = target_game.iloc[0]

            st.header(f"🔍 Analysis: Game {g_id}")
            
            # --- THE UPGRADE: Make names clickable if they are in our roster ---
            white_linked = make_clickable_name(meta['white_player'])
            black_linked = make_clickable_name(meta['black_player'])
            
# Display the linked names alongside their Elos
            st.subheader(f"{white_linked} ({int(meta['white_elo'])}) vs {black_linked} ({int(meta['black_elo'])})")
            
            # --- NEW: EXECUTIVE SUMMARY (Graph + Synopsis Side-by-Side) ---
            exec_col1, exec_col2 = st.columns(2)
            
            with exec_col1:
                # Display the static graph image (Left Side)
                img_path = find_exact_image(graphs_dir, g_id)
                if img_path:
                    st.image(img_path, use_container_width='stretch')
                else:
                    st.info("No graph image found for this game.")
                    
            with exec_col2:
                # Display the AI Synopsis (Right Side)
                if str(g_id) in game_synopses_dict:
                    game_info = game_synopses_dict[str(g_id)]
                    st.warning(f"**Critical Mistakes:** {game_info['blunders']}\n\n**Synopsis:** {game_info['synopsis']}")
                else:
                    st.info("No AI synopsis available for this game.")
            
            st.markdown("---") # A nice visual separator before the deep dive charts
            
            view_mode = st.radio("Chart Display Mode:", ["Combined", "White Only", "Black Only", "Stacked (Separate)"], horizontal=True)
            
            
            
            # ==========================================
            # MAIN LAYOUT COLUMNS
            # ==========================================
            col_left, col_right = st.columns([2, 1])

            # ------------------------------------------
            # LEFT BUCKET: Charts & Coach's Notes
            # ------------------------------------------
            with col_left:
                st.write("### Centipawn Performance")
                
                # ---------------------------------------------
                # 1. REPAIR NUMBERING & CALCULATE WIN PROBABILITY
                # ---------------------------------------------
                # THE FIX: The database has corrupted move_numbers for Black (shifted by +1).
                # Since our SQL query forces strict chronological order, we can completely ignore 
                # the database numbers and generate mathematically perfect Plies and Move Numbers from scratch!
                target_game['ply'] = range(1, len(target_game) + 1)
                target_game['move_number'] = (target_game['ply'] + 1) // 2
                
                target_game = target_game.sort_values(by='ply').copy()
                
                # Calculate the running cumulative win probability starting at 0.5
                target_game['wev_impact'] = target_game.apply(
                    lambda r: -r['wev'] if r['color'] == 'White' else r['wev'], axis=1
                )
                target_game['win_prob'] = (0.5 + target_game['wev_impact'].cumsum()).clip(0.0, 1.0)
                
                # ---------------------------------------------
                # 2. DRAW THE INTERACTIVE CHARTS
                # ---------------------------------------------
                # Now filter the data based on the slider, AFTER calculating the running probability
                plot_data = target_game[(target_game['wev'] >= wev_range[0]) & (target_game['wev'] <= wev_range[1])].copy()

                if view_mode == "White Only":
                    plot_data = plot_data[plot_data['color'] == 'White']
                    fig = px.line(plot_data, x="ply", y="win_prob", title="Win Expectancy (White)", markers=True)
                    fig.update_traces(line_color="blue")
                elif view_mode == "Black Only":
                    plot_data = plot_data[plot_data['color'] == 'Black']
                    fig = px.line(plot_data, x="ply", y="win_prob", title="Win Expectancy (Black)", markers=True)
                    fig.update_traces(line_color="red")
                elif view_mode == "Stacked (Separate)":
                    fig = px.line(plot_data, x="ply", y="win_prob", color="color", facet_row="color", title="Win Expectancy (Stacked)", markers=True)
                    fig.update_yaxes(matches=None) 
                else: 
                    fig = px.line(plot_data, x="ply", y="win_prob", color="color", title="Win Expectancy (Combined)", markers=True)

                fig.update_layout(yaxis_title="White Win Probability", xaxis_title="Ply", yaxis_range=[-0.05, 1.05])
                fig.add_hline(y=0.5, line_dash="dash", line_color="gray", opacity=0.5)
                st.plotly_chart(fig, use_container_width='stretch')     

                # ---------------------------------------------
                # 3. FILTER COACH'S NOTES
                # ---------------------------------------------
                # Fetch the lessons dictionary for this game
                lesson_dict = get_game_lessons_dict(g_id, selected_db_file)
                
                # FILTER: Keep notes where there is an annotation AND (WEV >= 0.10 OR contains "COACH" OR has a deep dive)
                notes_df = target_game[
                    (target_game['annotation'].notna()) & 
                    (target_game['annotation'] != "") & 
                    (
                        (target_game['wev'] >= 0.10) | 
                        (target_game['annotation'].str.contains("COACH", case=False, na=False)) |
                        (target_game['move_number'].isin(lesson_dict.keys()))
                    )
                ]
                
                # SAFETY CHECK: Do we actually have a Summary or Deep Dives to show?
                has_summary = any("COACH" in str(x).upper() for x in notes_df['annotation'])
                has_lessons = len(lesson_dict) > 0
                
                # Only draw the header and the loop IF there are actual Coach's Notes, a Summary, or standard engine blunders
                if has_summary or has_lessons or not notes_df.empty:
                    st.write("### Coach's Notes")

                    # --- THIS IS THE DISPLAY LOOP THAT WENT MISSING ---
                    for index, row in notes_df.iterrows():
                        note_text = str(row['annotation'])
                        current_move_num = int(row['move_number'])
                        
                        # 1. Print the AI Coach's Summary (looks for the word "COACH")
                        if "COACH" in note_text.upper():
                            st.success(note_text)
                        
                        # 2. Print regular Engine Evaluations & Tactical Blunders
                        else:
                            color_emoji = "⚪" if row['color'] == 'White' else "⚫"
                            st.info(f"{color_emoji} **Move {current_move_num}**: {note_text}")

            # 3. Print the AI Deep Dive if one exists for this specific move
                        if current_move_num in lesson_dict:
                            with st.expander(f"📖 Read Coach's Deep Dive (Move {current_move_num})"):
                                lesson_text = lesson_dict[current_move_num]
                                
                                # ==========================================
                                # UX FIX: DOWNSIZE THE METADATA HEADERS
                                # ==========================================
                                # This intercepts massive # (H1) or ## (H2) headers at the top of the file 
                                # and shrinks them to ### (H3) so they perfectly match the Analysis text size!
                                lesson_text = re.sub(r'^#{1,2}\s+(LESSON)', r'### \1', lesson_text, flags=re.MULTILINE)
                                lesson_text = re.sub(r'^#{1,2}\s+(Players:)', r'### \1', lesson_text, flags=re.MULTILINE)
                                lesson_text = re.sub(r'^#{1,2}\s+(Opening:)', r'### \1', lesson_text, flags=re.MULTILINE)
                                
                                # Print the text taking up the full width
                                st.markdown(lesson_text)
                                
                                # The Trigger Button (with the unique key fix!)
                                if st.button(f"🎯 Analyze Move {current_move_num} Sequence on Mini-Board", key=f"mini_board_btn_{index}", use_container_width='stretch'):
                                    st.session_state.active_sequence_text = lesson_text
                                    
            # ------------------------------------------
            # RIGHT BUCKET: Interactive Board & Textbook
            # ------------------------------------------
            with col_right:
                # ==========================================
                # UX FIX: THE STICKY ANCHOR
                # ==========================================
                # 1. Drop a hidden HTML ID into this specific column
                st.markdown("<div id='sticky-anchor'></div>", unsafe_allow_html=True)
                
                # 2. Command the browser to ONLY make the column containing this anchor sticky!
                st.markdown("""
                    <style>
                        /* We check for both 'stColumn' and 'column' just in case Streamlit updates its tags! */
                        div[data-testid="stColumn"]:has(#sticky-anchor),
                        div[data-testid="column"]:has(#sticky-anchor) {
                            position: sticky;
                            top: 4rem; /* Floats just below the top edge of the screen */
                            align-self: flex-start; /* Detaches it from the left column's height */
                            z-index: 10; /* Keeps it above other elements */
                        }
                    </style>
                """, unsafe_allow_html=True)
                
                st.write("### Interactive Board")
                # [The rest of your Interactive Board code continues here...]               
                
                
                
                
                # THE FIX: Use 'ply' instead of 'move_number' so Black's moves aren't hidden by duplicates!
                plies = target_game['ply'].tolist()

                if plies:
                    # 1. CREATE THE SLIDER & GET DATA FIRST
                    if 'scrubber' not in st.session_state or st.session_state.scrubber not in plies:
                        st.session_state.scrubber = plies[0]
                    
                    selected_ply = st.select_slider("Select Ply:", options=plies, key="scrubber")
                    
                    # Because ply is unique (1, 2, 3, 4...), iloc[0] will now perfectly grab Black's move on even numbers!
                    move_data = target_game[target_game['ply'] == selected_ply].iloc[0]
                    
                    # 2. NEW LICHESS API CHECK
                    if 'piece_count' in move_data and move_data['piece_count'] <= 7:
                        if st.button("🔍 Live Query Lichess 7-Piece Tablebase", use_container_width='stretch'):
                            with st.spinner("Consulting the Oracle..."):
                                tb_data = query_lichess_tablebase(move_data['fen'])
                                
                                if "error" in tb_data:
                                    st.error(f"Could not reach Tablebase: {tb_data['error']}")
                                else:
                                    category = tb_data.get('category', 'unknown')
                                    dtz = tb_data.get('dtz', 'N/A')
                                    dtm = tb_data.get('dtm', 'N/A')
                                    tb_moves = tb_data.get('moves', [])
                                    
                                    if category in ['win', 'maybe-win']:
                                        st.success(f"📈 **Lichess API Result: WIN**")
                                    elif category in ['loss', 'maybe-loss']:
                                        st.error(f"📉 **Lichess API Result: LOSS**")
                                    else:
                                        st.warning(f"⚖️ **Lichess API Result: DRAW**")
                                    
                                    col_dtz, col_dtm = st.columns(2)
                                    with col_dtz:
                                        st.write(f"**DTZ (Zero):** {dtz} plies")
                                    with col_dtm:
                                        if dtm is not None:
                                            st.write(f"**DTM (Mate):** {abs(dtm)} plies")
                                        
                                    if tb_moves:
                                        best_move = tb_moves[0].get('san', 'Unknown')
                                        st.write(f"🌟 **Absolute Best Engine Move:** `{best_move}`")
                        st.markdown("---") 

                #3. DRAW THE VISUAL CHESSBOARD & EVAL BAR
                    board = chess.Board(move_data['fen'])

                    # THE FIX: The FEN is the board BEFORE the move. We digitally play the move so you can see it!
                    last_move = None
                    try:
                        # Strip punctuation like '!' or '?' so the chess library doesn't crash
                        clean_san = str(move_data['notation']).replace('!', '').replace('?', '')
                        board.push_san(clean_san)
                        last_move = board.peek() # Save the exact square to highlight it!
                    except:
                        pass

                    # A. Parse the raw Engine Eval (e.g., "+1.5", "-0.8", "M3", "-M2")
                    white_percentage = 50.0  # Default to exactly 50/50 for a tie or missing data

                    try:
                        eval_str = str(move_data['engine_eval']).strip()

                        if pd.notna(move_data['engine_eval']) and eval_str != "":
                            if 'M' in eval_str.upper():
                                # Handle Forced Mates
                                if '-' in eval_str:
                                    white_percentage = 0.0    # Black has forced mate
                                else:
                                    white_percentage = 100.0  # White has forced mate
                            else:
                                # Handle Standard Evaluation (e.g., +1.5 or -2.0)
                                eval_float = float(eval_str)
                                # Cap the visual bar at +5 and -5 pawns
                                # Formula: 50% base + (eval * 10). So +5.0 = 100%, -5.0 = 0%
                                white_percentage = 50 + (eval_float * 10)
                                white_percentage = max(0, min(100, white_percentage))
                    except:
                        pass # If anything goes wrong, it gracefully defaults to 50/50

                    # B. Create two columns: one wide one for the board, one narrow one for the Eval Bar
                    board_col, eval_col = st.columns([350, 40])

                    with board_col:
                        # THE FIX: We pass 'lastmove' to the SVG drawer so it physically highlights the square!
                        st.markdown(chess.svg.board(board=board, size=350, lastmove=last_move), unsafe_allow_html=True)
                        st.caption(f"**Move {move_data['move_number']}:** {move_data['color']} played {move_data['notation']}")
                        
                    with eval_col:
                        # C. Draw the custom HTML Eval Bar
                        eval_bar_html = f"""
                        <div style="
                            height: 350px; 
                            width: 25px; 
                            background-color: #333333; /* Dark color for Black */
                            border-radius: 4px; 
                            border: 1px solid #555;
                            position: relative; 
                            overflow: hidden;
                        ">
                            <div style="
                                position: absolute; 
                                bottom: 0; 
                                width: 100%; 
                                height: {white_percentage}%; 
                                background-color: #f0f0f0; /* Light color for White */
                                transition: height 0.4s ease-in-out;
                            "></div>
                        </div>
                        """
                        st.markdown(eval_bar_html, unsafe_allow_html=True)
                        
                        
                        
                    # 4. LOCAL TABLEBASE CHECK
                    if 'tb_wdl' in move_data and pd.notna(move_data['tb_wdl']):
                        wdl_val = move_data['tb_wdl']
                        dtz_val = move_data['tb_dtz']
                        
                        if wdl_val == 2: tb_status = "Local Tablebase Result: White is winning"
                        elif wdl_val == -2: tb_status = "Local Tablebase Result: Black is winning"
                        elif wdl_val == 0: tb_status = "Local Tablebase Result: Dead Draw"
                        else: tb_status = "Local Tablebase Result: Draw (50-move rule/Cursed win)"
                        
                        st.info(f"📚 **{tb_status}** | Distance to Mate/Zero: {int(dtz_val)} plys")

                    # 5. RENDER CURRENT MOVE ANNOTATION
                    if pd.notna(move_data['annotation']) and move_data['annotation'] != "":
                        note_text = move_data['annotation']
                        if "COACH SUMMARY" not in note_text: st.error(f"{note_text}")
                
                # 6. TEXTBOOK BOARD DISPLAY TOGGLE 
                if 'pawn_structure' in meta and pd.notna(meta['pawn_structure']):
                    struct_name = meta['pawn_structure']
                    if struct_name in TEXTBOOK_STRUCTURES:
                        st.markdown("---")
                        st.write(f"### 📘 Textbook: {struct_name}")
                        if st.toggle(f"Show {struct_name} Skeleton"):
                            t_fen = TEXTBOOK_STRUCTURES[struct_name]
                            t_board = chess.Board(t_fen)
                            st.markdown(chess.svg.board(board=t_board, size=350), unsafe_allow_html=True)
                            st.caption(f"Idealized pawn skeleton for **{struct_name}**.")

                # ==========================================
                # RECEPTION AREA: MINI-SEQUENCE BOARD
                # ==========================================
                st.markdown("---") # Clean visual divider separating the main board
                
                # Check if a user clicked the trigger button on the left
                if 'active_sequence_text' in st.session_state:
                    
                    # The forgiving Regex that handles missing move numbers
                    extracted_fens = re.findall(
                        r"([rnbqkpRNBQKP1-8]+\/[rnbqkpRNBQKP1-8]+\/[rnbqkpRNBQKP1-8]+\/[rnbqkpRNBQKP1-8]+\/[rnbqkpRNBQKP1-8]+\/[rnbqkpRNBQKP1-8]+\/[rnbqkpRNBQKP1-8]+\/[rnbqkpRNBQKP1-8]+\s+[wb]\s+(?:[KQkq]{1,4}|-)\s+(?:[a-h][1-8]|-)(?:\s+\d+\s+\d+)?)", 
                        st.session_state.active_sequence_text
                    )

                    if extracted_fens:
                        st.write("### Deep Dive Sequence")
                        
                        step = st.select_slider(
                            "Scrub Position:", 
                            options=range(len(extracted_fens)), 
                            format_func=lambda x: f"Position {x+1}", 
                            key="global_mini_slider"
                        )
                        
                        mini_board = chess.Board(extracted_fens[step].strip())
                        st.markdown(chess.svg.board(board=mini_board, size=350), unsafe_allow_html=True)
                        
                        # The Close Button to clear the memory
                        if st.button("❌ Close Mini-Board"):
                            del st.session_state.active_sequence_text
                            st.rerun() 
                            
                    else:
                        st.warning("⚠️ No valid FEN sequence detected in this specific analysis.")
                else:
                    st.info("💡 Open a Coach's Deep Dive on the left and click 'Analyze Sequence' to load the mini-board here.")



                # 7. NAVIGATION BUTTONS (Now safely inside col_right!)
                st.markdown("<br>", unsafe_allow_html=True)
                btn_col1, btn_col2, btn_col3 = st.columns(3)
                with btn_col1:
                    if st.button("⬆️ Scroll to Gallery", use_container_width='stretch'):
                        st.session_state.scroll_target = 'gallery-top'
                        st.rerun()
                with btn_col2:
                    if st.button("❌ Close Analysis", use_container_width='stretch', type='primary'):
                        st.session_state.analyzed_game_id = None
                        st.session_state.scroll_target = 'gallery-top'
                        st.rerun()
                with btn_col3:
                    # THE FIX: We pull the video link safely from the 'target_game' DataFrame
                    video_link = None
                    if 'video_url' in target_game.columns:
                        video_link = target_game['video_url'].iloc[0] 

                    # Check if the URL actually exists before drawing the button
                    if pd.notna(video_link) and str(video_link).strip() != "":
                        st.link_button("🎬 idChess Video", url=str(video_link), use_container_width='stretch')
                        
                    
                    
                    
                    
    # --- TAB 2: THE POLGAR GLOSSARY ---
    with tab2:
        st.header("📚 Middlegame Motif Glossary")
        st.write("Explore classic tactical themes and structures based on László Polgár's methodology.")
        
        # Create a dropdown menu using our new dictionary
        selected_theme = st.selectbox("Select a Tactical Theme:", list(POLGAR_THEMES.keys()))
        
        # Extract the FEN and the Explanation from the nested dictionary
        theme_fen = POLGAR_THEMES[selected_theme]["fen"]
        theme_explanation = POLGAR_THEMES[selected_theme]["explanation"]
        
        # Display the FEN on a chessboard
        board = chess.Board(theme_fen)
        st.markdown(chess.svg.board(board=board, size=400), unsafe_allow_html=True)
        
        # Display the targeted explanation
        st.success(f"**The Concept:** {theme_explanation}")
        
        if theme_fen == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1":
            st.warning("*(Note: Exact tactical FEN for this theme is pending generation in our next update)*")

    # ==========================================
    # --- TAB 3: THE ENDGAME ENCYCLOPEDIA ---
    # ==========================================
    with tab3:
        st.header("🏁 Endgame Encyclopedia")
        st.write("Master the Top 20 theoretical endgame positions based on classical endgame manuals.")
        
        # Create a dropdown menu using our endgame dictionary
        selected_endgame = st.selectbox("Select a Theoretical Endgame:", list(ENDGAME_THEMES.keys()))
        
        # Extract the FEN and Explanation
        endgame_fen = ENDGAME_THEMES[selected_endgame]["fen"]
        endgame_explanation = ENDGAME_THEMES[selected_endgame]["explanation"]
        
        # Display the FEN on a chessboard
        endgame_board = chess.Board(endgame_fen)
        st.markdown(chess.svg.board(board=endgame_board, size=400), unsafe_allow_html=True)
        
        # Display the explanation
        st.success(f"**The Concept:** {endgame_explanation}")

    # --- 7. Execute Javascript Scrolling ---
    if st.session_state.scroll_target:
        js = f"""
        <script>
            const doc = window.parent.document;
            const el = doc.getElementById('{st.session_state.scroll_target}');
            if (el) {{
                el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
            }}
        </script>
        """
        components.html(js, height=0)
        st.session_state.scroll_target = None

if __name__ == "__main__":
    main()