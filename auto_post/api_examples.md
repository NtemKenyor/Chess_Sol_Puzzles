curl -X POST http://127.0.0.1:5000/social-media/facebook   -H "Content-Type: application/json"   -d '{
    "link_2_post": "https://roynek.com/Chess_Sol_Puzzles/public/?puzzle=0aMK7",
    "message": "More on chess🚀",
    "media": "https://roynek.com/Chess_Sol_Puzzles/auto_post/output_video/chess_short.mp4",
    "pages_ordered_ids": "7"
  }'


curl -X POST https://roynek.com/alltrenders/codes/python_API/social-media/facebook \
  -H "Content-Type: application/json" \
  -d '{
    "link_2_post": "https://roynek.com",
    "message": "Testing Facebook video post via local API 🚀",
    "media": "https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4",
    "pages_ordered_ids": "7"
  }'


curl -X POST https://roynek.com/alltrenders/codes/python_API/social-media/facebook \
  -H "Content-Type: application/json" \
  -d '{"link_2_post":"https://roynek.com","message":"Testing Facebook video post via local API","media":"https://roynek.com/Chess_Sol_Puzzles/auto_post/output_video/chess_short.mp4","pages_ordered_ids":"7"}'


curl -X POST http://127.0.0.1:5000/social-media/x   -H "Content-Type: application/json"   -d '{"link_2_post":"https://roynek.com/Chess_Sol_Puzzles/public/?puzzle=0aMK7","message":"Testing Facebook video post via local API","media":"https://roynek.com/Chess_Sol_Puzzles/auto_post/output_video/chess_short.mp4","pages_ordered_ids":"21", "comm_id": "1578034816620310528"}'