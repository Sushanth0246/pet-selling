-- 1_create_pet_adoption.sql
CREATE DATABASE IF NOT EXISTS hero;
USE hero;

-- USERS

 CREATE TABLE  IF NOT EXISTS LoginS (
    
    Username VARCHAR(100) NOT NULL UNIQUE,
    Password VARCHAR(255) NOT NULL
    
 );
CREATE TABLE IF NOT EXISTS Users (
    UserID INT AUTO_INCREMENT PRIMARY KEY,
    Name VARCHAR(100) NOT NULL,
    Email VARCHAR(150) NOT NULL UNIQUE,
    Phone VARCHAR(20),
    Address VARCHAR(255),
    Password VARCHAR(255) NOT NULL,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- OWNERS
CREATE TABLE IF NOT EXISTS Owners (
    OwnerID INT AUTO_INCREMENT PRIMARY KEY,
    Name VARCHAR(100) NOT NULL,
    Email VARCHAR(150) NOT NULL UNIQUE,
    Contact VARCHAR(20),
    Address VARCHAR(255),
    Password VARCHAR(255) NOT NULL,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PETS
CREATE TABLE IF NOT EXISTS Pets (
    PetID INT AUTO_INCREMENT PRIMARY KEY,
    OwnerID INT NOT NULL,
    Name VARCHAR(100),
    Breed VARCHAR(100),
    Type VARCHAR(50),
    Age INT,
    Gender ENUM('Male','Female','Unknown') DEFAULT 'Unknown',
    Color VARCHAR(50),
    Size VARCHAR(50),
    ForSale BOOLEAN DEFAULT FALSE,
    ForGrooming BOOLEAN DEFAULT FALSE,
    Description TEXT,
    ImageURL VARCHAR(255),
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (OwnerID) REFERENCES Owners(OwnerID) ON DELETE CASCADE
);

-- ADOPTION REQUESTS
CREATE TABLE IF NOT EXISTS AdoptionRequests (
    ReqID INT AUTO_INCREMENT PRIMARY KEY,
    UserID INT NOT NULL,
    PetID INT NOT NULL,
    Message TEXT,
    Status ENUM('Pending','Approved','Rejected') DEFAULT 'Pending',
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE,
    FOREIGN KEY (PetID) REFERENCES Pets(PetID) ON DELETE CASCADE
);

-- PAYMENTS
CREATE TABLE IF NOT EXISTS Payments (
    PaymentID INT AUTO_INCREMENT PRIMARY KEY,
    ReqID INT NOT NULL,
    UserID INT NOT NULL,
    OwnerID INT NOT NULL,
    Mode ENUM('Cash','Online','Donate') NOT NULL,
    Amount DECIMAL(10,2) DEFAULT 0.00,
    Date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ReqID) REFERENCES AdoptionRequests(ReqID) ON DELETE CASCADE,
    FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE,
    FOREIGN KEY (OwnerID) REFERENCES Owners(OwnerID) ON DELETE CASCADE
);

-- ADOPTION HISTORY
CREATE TABLE IF NOT EXISTS AdoptionHistory (
    AdoptionID INT AUTO_INCREMENT PRIMARY KEY,
    UserID INT NOT NULL,
    PetID INT NOT NULL,
    OwnerID INT NOT NULL,
    PaymentID INT,
    Date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE,
    FOREIGN KEY (PetID) REFERENCES Pets(PetID) ON DELETE CASCADE,
    FOREIGN KEY (OwnerID) REFERENCES Owners(OwnerID) ON DELETE CASCADE,
    FOREIGN KEY (PaymentID) REFERENCES Payments(PaymentID) ON DELETE SET NULL
);

-- Optional: sample owner, user and pet
INSERT INTO Owners (Name, Email, Contact, Address, Password)
VALUES ('Alice Owner', 'alice.owner@example.com', '9876543210', 'Owner Street, City', 'changeme');

INSERT INTO Users (Name, Email, Phone, Address, Password)
VALUES ('Bob User', 'bob.user@example.com', '9123456780', 'User Road, City', 'changeme');

-- Note: replace plain passwords by hashed ones when inserting directly
