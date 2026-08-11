# Image Handler E2E Validation Checklist

| Slide | Archetype | Images | Fields | Placeholder idx | Orientation | Expected behaviour |
|---:|---|---|---|---|---|---|
| 1 | image_right | FY27 Ai Image (1).jpg | picture | 20 | landscape | single landscape image; letterboxing and placeholder geometry check |
| 2 | quote | FY27 Public Sector (11).jpg | headshot | 30 | portrait | quote headshot image insertion |
| 3 | team | FY27 General Tech & IT (37).jpg<br>FY27 Public Sector (36).jpg<br>FY27 Education (10).jpg | member_picture[0]<br>member_picture[1]<br>member_picture[2] | 20<br>21<br>22 | portrait<br>portrait<br>landscape | three images on one slide; member_picture occurrence mapping |
| 4 | logo_wall | FY27 People Collaborating & Corporate (77).jpg<br>FY27 Data & Security (37).jpg<br>FY27 General Tech & IT (38).jpg<br>FY27 Healthcare (9).jpg | logo[0]<br>logo[1]<br>logo[2]<br>logo[3] | 20<br>21<br>22<br>23 | square<br>square<br>landscape<br>portrait | multiple images on one slide; logo occurrence mapping |
| 5 | image_right | FY27 Ai Image (1).jpg | picture | 20 | landscape | repeated image usage for cache validation |