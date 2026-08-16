# Title and Metadata
LearnKoreanWords

Author: Bin An

Status: Draft

Date: 08/15/2026

## Context and Scope

Korean-English vocabulary flashcard generator geared towards children.  Flashcards will at minimum contain a Korean word and its English translation and a photo of that word; ideally, the flashcard will also contain a soundbyte of the word's pronunciation in Korean.  


## Requirements

Korean-English word pairs pulled and cross-referenced(?) from the following sources: 

(1) Tatoeba sentences
(2) Wiki list that Srikar found for me 
**Might want to find another source geared towards kids learning and matches those words against those found in the first two?
(3) Some type of Image generator or scraper to append a photo of the vocabulary word in question if one does not already exist from one the two sources listed above


## High-Level Design

Pulling words from the following databases based on frequency/usage: 

(1) Tatoeba
(2) Wiki

In this version, we will first choose the 100 most used nouns, 


## Detailed Design

API Endpoints: 

(a) Tatoeba
(b) Wiki
(c) 


Data Models: 



Database Schemas: 

We've discussed using CSV to store the lists instead of using json.  Easier to deal with the data.  


## Alternatives and Trade-offs

We considered a more direct approach to Korean-to-English translation a la Google Translate, but at the risk of having to manually check whether the translation was correct, based on a simple attempted translation of the word "cat," which was an utter failure, I decided that starting from two already-compiled, clean databases would be a good start.  I'm open to moving to this approach once a working version of the program has been established


## Execution Plan

Monitor and Logging:



Rollout and Migration

Is this where I need to put it on a website or something?