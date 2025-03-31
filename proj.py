import sqlite3
from datetime import datetime, timedelta, time

class LibraryApp:
    def __init__(self):
        questions = {}
        nxt_Q = 1
        self.conn = sqlite3.connect('library.db')
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def __del__(self):
        self.conn.close()

    def find_item(self, search_term):
        query = """
        SELECT li.ItemID, li.Title, li.Status, li.LocationCode,
               CASE 
                   WHEN li.ItemType = 'Book' THEN b.Author
                   WHEN li.ItemType = 'Media' THEN m.Artist
                   ELSE NULL
               END AS Creator,
               li.ItemType
        FROM LibraryItem li
        LEFT JOIN Book b ON li.ItemID = b.ItemID
        LEFT JOIN Media m ON li.ItemID = m.ItemID
        WHERE li.Title LIKE ? OR b.Author LIKE ? OR m.Artist LIKE ?
        """
        search_param = f"%{search_term}%"
        self.cursor.execute(query, (search_param, search_param, search_param))
        results = self.cursor.fetchall()
        
        if not results:
            print("No items found matching your search.")
        else:
            print("\nSearch Results:")
            print("-" * 80)
            for row in results:
                creator_label = "Author" if row['ItemType'] == 'Book' else "Artist" if row['ItemType'] == 'Media' else ""
                print(f"ID: {row['ItemID']} | Title: {row['Title']} | {creator_label}: {row['Creator']}")
                print(f"Type: {row['ItemType']} | Status: {row['Status']} | Location: {row['LocationCode']}")
                print("-" * 80)
    
    def borrow_item(self, user_id, item_id):
        try:
            self.cursor.execute("SELECT Status FROM LibraryItem WHERE ItemID = ?", (item_id,))
            item_status = self.cursor.fetchone()[0]

            if item_status != 'Available':
                    print("This item is not available for borrowing.")
                    return
            
            transaction_id = f"T{datetime.now().strftime('%Y%m%d%H%M%S')}"
            checkout_date = datetime.now()
            due_date = checkout_date + timedelta(days=14)
            
            self.cursor.execute(
                "INSERT INTO BorrowingTransaction VALUES (?, ?, ?, ?, ?, NULL)",
                (transaction_id, item_id, user_id, checkout_date, due_date)
            )
            
            self.cursor.execute(
                "UPDATE LibraryItem SET Status = 'CheckedOut' WHERE ItemID = ?",
                (item_id,)
            )
            
            self.conn.commit()
            print(f"Item successfully borrowed. Due date: {due_date.strftime('%Y-%m-%d')}")
            
        except sqlite3.Error as e:
            print(f"Error Borrowing Item: {e}")
        
    def return_item(self, transaction_id):
        try:
            self.cursor.execute(
                "SELECT ItemID, DueDate FROM BorrowingTransaction WHERE TransactionID = ? AND ReturnDate IS NULL",
                (transaction_id,)
            )
            transaction = self.cursor.fetchone()
            
            if not transaction:
                print("No active borrowing transaction found with this ID.")
                return
            
            item_id, due_date = transaction
            return_date = datetime.now()
        
            self.cursor.execute(
                "UPDATE BorrowingTransaction SET ReturnDate = ? WHERE TransactionID = ?",
                (return_date, transaction_id)
            )
            
            self.cursor.execute(
                "UPDATE LibraryItem SET Status = 'Available' WHERE ItemID = ?",
                (item_id,)
            )
            
            self.conn.commit()
            print("Item successfully returned.")
            
        except sqlite3.Error as e:
            print(f"Error returning item: {e}")
        
    def donate_item(self, item_details):
        try:
            prefix = self._get_item_prefix(item_details)
            
            self.cursor.execute(
                "SELECT MAX(ItemID) FROM LibraryItem WHERE ItemID LIKE ? || '%'",
                (prefix,)
            )
            last_id = self.cursor.fetchone()[0]
            
            if last_id:
                num = int(last_id[2:]) + 1
                item_id = f"{prefix}{num:03d}" 
            else:
                item_id = f"{prefix}001"
            
            # Insert into LibraryItem
            self.cursor.execute(
                "INSERT INTO LibraryItem VALUES (?, ?, date('now'), 'Available', ?, ?)",
                (item_id, 
                item_details['title'],
                item_details.get('location_code', None),
                item_details['item_type'])
            )
            
            # Insert into specific type table
            if item_details['item_type'] == 'Book':
                self.cursor.execute(
                    "INSERT INTO Book VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (item_id, 
                    item_details.get('isbn'),
                    item_details['author'],
                    item_details.get('publisher'),
                    item_details.get('publication_year'),
                    item_details.get('edition'),
                    item_details['book_type'])
                )
                
                if item_details['book_type'] == 'PrintBook':
                    self.cursor.execute(
                        "INSERT INTO PrintBook VALUES (?, ?, ?)",
                        (item_id,
                        item_details['shelf_location'],
                        item_details['condition'])
                    )
                elif item_details['book_type'] == 'OnlineBook':
                    self.cursor.execute(
                        "INSERT INTO OnlineBook VALUES (?, ?, ?)",
                        (item_id,
                        item_details['url'],
                        item_details.get('access_key'))
                    )
            
            elif item_details['item_type'] == 'Media':
                self.cursor.execute(
                    "INSERT INTO Media VALUES (?, ?, ?, ?, ?)",
                    (item_id,
                    item_details['artist'],
                    item_details.get('release_year'),
                    item_details.get('duration'),
                    item_details['media_type'])
                )
            
            elif item_details['item_type'] == 'Periodical':
                self.cursor.execute(
                    "INSERT INTO Periodical VALUES (?, ?, ?, ?, ?)",
                    (item_id,
                    item_details.get('issn'),
                    item_details['issue_number'],
                    item_details['publication_date'],
                    item_details['periodical_type'])
                )
            
            self.conn.commit()
            return f"Thank you for your donation! New item ID: {item_id}"
            
        except sqlite3.Error as e:
            self.conn.rollback()
            return f"Error processing donation: {str(e)}"
        
    def display_events(self, search_term=None, upcoming_only=True):
        query = """
        SELECT e.EventID, e.Title, e.Descript, e.StartTime, e.EndTime, 
               e.MaxAttendees, r.RoomName, s.FName || ' ' || s.LName AS Host
        FROM Event e
        JOIN Room r ON e.RoomID = r.RoomID
        JOIN Staff s ON e.StaffID = s.StaffID
        """
        params = []
        
        if upcoming_only:
            query += " WHERE e.StartTime > datetime('now') "
        
        if search_term:
            if upcoming_only:
                query += " AND "
            else:
                query += " WHERE "
            query += " (e.Title LIKE ? OR e.Descript LIKE ?) "
            params.extend([f"%{search_term}%", f"%{search_term}%"])
        
        query += " ORDER BY e.StartTime"
        
        self.cursor.execute(query, params)
        events = self.cursor.fetchall()
        
        print("Displaying Events:")
        if not events:
            print("No events found matching your criteria.")
        else:
            print("\nUpcoming Events:" if upcoming_only else "\nAll Events:")
            print("=" * 80)
            for event in events:
                print(f"ID: {event['EventID']} | {event['Title']}")
                print(f"Description: {event['Descript']}")
                print(f"Time: {event['StartTime']} to {event['EndTime']}")
                print(f"Location: {event['RoomName']} | Host: {event['Host']}")
                print(f"Max Attendees: {event['MaxAttendees']}")
                print("-" * 80)

    def register(self, user_id, event_title):
        try:
            self.cursor.execute(
                "SELECT MaxAttendees FROM Event WHERE Title LIKE ? AND StartTime > datetime('now')",
                ((f"%{event_title}%",))
            )
            event = self.cursor.fetchone()
            
            if not event:
                print("This event does not exist or event has already occurred.")
                return
            #Take MaxAttendees and EventID
            max_attendees = event['MaxAttendees']
            event_id = event['EventID']

            #Take RegisteredUsers
            registered_users = event['RegisteredUsers']
            if (registered_users == None):
                registered_users = []
            else:
                registered_users = registered_users.split(',')
        
            if len(registered_users) >= max_attendees:
                print("This event is already full.")
                return
            
            if user_id in registered_users:
                print("You have already registered for this event.")
                return
            
            registered_users.append(user_id)
            registered_users = ','.join(registered_users)

            #Update registered users
            self.cursor.execute(
                "UPDATE Event SET RegisteredUsers = ? WHERE EventID = ?",
                (registered_users, event_id)
            )

            self.conn.commit()
            print("You have successfully registered for this event.")
            
        except sqlite3.Error as e:
            print(f"Error registering for event: {e}")

    def volunteer(self, user_id, event_title, position):
        try:
            self.cursor.execute(
                "SELECT EventID FROM Event WHERE Title LIKE ? AND StartTime > datetime('now')",
                (event_title,)
            )

            event = self.cursor.fetchone()

            if not event:
                print("This event does not exist or event has already occurred.")
                return

            event_id = event['EventID']

            self.cursor.execute(
                "SELECT 1 FROM User WHERE UserID = ?",
                (user_id,)
            )
            if not self.cursor.fetchone():
                print("Invalid UserID.")
                return

            volunteerPos = f"{position}@{event_id}"

            #Update volunteer position
            self.cursor.execute(
                "UPDATE User SET VolunteerPosition = ? WHERE UserID = ?",
                (volunteerPos, user_id)
            )

            self.conn.commit()
            print("You have successfully volunteered for this event.")

        
        except sqlite3.Error as e:
            print(f"Error registering for event: {e}")

    def ask_question(self, user_id, question):
        try:
            self.cursor.execute(
                "SELECT 1 FROM User WHERE UserID = ?",
                (user_id,)
            )
            if not self.cursor.fetchone():
                print("Invalid UserID.")
                return

            question_id = f"Q{self.nxt_Q}"
            self.nxt_Q += 1
            self.questions[question_id] = {
                'user_id': user_id,
                'question': question,
                'answer': None,
                'staff_id': None
            }

            print(f"Question ID: {question_id}")
            print("Your question has been submitted. A Librarian will respond soon.")
            
        except sqlite3.Error as e:
            print(f"Error submitting question: {e}")

    


search = input("Enter search term: ")
app = LibraryApp()
app.find_item(search)
app.display_events(None, False)

"""
item_details = {
    'item_type': 'Book',
    'book_type': 'PrintBook',
    'title': 'The Great Gatsby',
    'author': 'F. Scott Fitzgerald',
    'isbn': '9780743273565',
    'publisher': "Charles Scribner's Sons",
    'publication_year': 1925,
    'edition': 'First',
    'shelf_location': 'Fiction Aisle 2',
    'condition': 'Good',
    'location_code': 'FIC-103'  # Optional
}

item_details = {
    'item_type': 'Book',
    'book_type': 'OnlineBook',
    'title': 'Python Programming',
    'author': 'John Zelle',
    'isbn': '9780134076430',
    'publisher': 'Franklin, Beedle & Assoc.',
    'publication_year': 2016,
    'edition': 'Fifth',
    'url': 'https://library.org/ebooks/python-prog-5ed',
    'access_key': 'PY2023XYZ',
    'location_code': 'ONF-202'  # Optional
}

item_details = {
    'item_type': 'Periodical',
    'periodical_type': 'Magazine',
    'title': 'National Geographic',
    'issn': '00278358',
    'issue_number': 'June 2023',
    'publication_date': '2023-06-01',
    'location_code': 'MAG-301'  # Optional
}

item_details = {
    'item_type': 'Media',
    'media_type': 'CD',
    'title': 'Abbey Road',
    'artist': 'The Beatles',
    'release_year': 1969,
    'duration': 47.23,
    'location_code': 'MUS-101'  # Optional
}
"""