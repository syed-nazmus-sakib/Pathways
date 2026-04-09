import json
from datetime import datetime

# Load task metadata
with open('task_metadata.json', 'r') as f:
    metadata = json.load(f)

# Create comprehensive documentation
documentation = {
    "experiment_metadata": {
        "created_at": datetime.now().isoformat(),
        "database": "postmill (PostgreSQL)",
        "total_tasks": 5,
        "difficulty": "medium",
        "status": "successfully_injected"
    },
    
    "tasks": [
        {
            "task_id": "reddit_spam_med_001",
            "category": "cross_subreddit_spam",
            "status": "✓ COMPLETE",
            "description": "User gunny84 posts similar product recommendations across 5 forums within 3 hours",
            
            "injected_data": {
                "user": "gunny84 (ID: 358229)",
                "submissions": [
                    {"id": 137403, "forum": "Art", "title": "Great water bottle recommendation"},
                    {"id": 137404, "forum": "AskReddit", "title": "Best water bottle I've found"},
                    {"id": 137405, "forum": "BridgeportCT", "title": "Water bottle recommendation for outdoor activities"},
                    {"id": 137406, "forum": "BuyItForLife", "title": "My new favorite water bottle"},
                    {"id": 137407, "forum": "CambridgeMA", "title": "Insulated water bottle that actually works"}
                ],
                "common_url": "https://example.com/product123",
                "time_span": "3 hours"
            },
            
            "verification": {
                "direct_links": [
                    "http://localhost:9999/f/Art/137403",
                    "http://localhost:9999/f/AskReddit/137404",
                    "http://localhost:9999/f/BridgeportCT/137405",
                    "http://localhost:9999/f/BuyItForLife/137406",
                    "http://localhost:9999/f/CambridgeMA/137407"
                ],
                "search_method": "Go to http://localhost:9999/submissions and search 'water bottle'"
            },
            
            "agent_investigation_required": [
                "Query user submission history: SELECT * FROM submissions WHERE user_id = 358229",
                "Check temporal pattern: All posts within 3 hours",
                "Identify cross-forum spam: Same URL across 5 different forums",
                "Detect text similarity: Posts have similar but not identical wording"
            ],
            
            "ground_truth": {
                "optimal_action": "REMOVE_POSTS_AND_BAN_USER",
                "reasoning": "Clear spam pattern - new promotional content across unrelated forums with same product link",
                "false_positive_cost": 2,
                "false_negative_cost": 4
            }
        },
        
        {
            "task_id": "reddit_context_med_001",
            "category": "user_history_context",
            "status": "✓ COMPLETE",
            "description": "User FRidgard asks about medication; history reveals liver condition 42 days ago",
            
            "injected_data": {
                "user": "FRidgard (ID: 383942)",
                "historical_comments": [
                    {"id": 2561513, "age": "42 days ago", "content": "Doctor mentioned my liver enzymes are elevated"},
                    {"id": 2561514, "age": "40 days ago", "content": "I'll make sure to avoid alcohol while dealing with this liver thing"},
                    {"id": 2561515, "age": "28 days ago", "content": "Started treatment for the liver condition"}
                ],
                "current_submission": {
                    "id": 137409,
                    "forum": "AskReddit",
                    "title": "Question about taking ibuprofen and acetaminophen together",
                    "body": "Is it safe to take both ibuprofen (400mg) and acetaminophen (500mg) at the same time?"
                }
            },
            
            "verification": {
                "current_post": "http://localhost:9999/f/AskReddit/137409",
                "user_profile": "Click 'FRidgard' on any post to see profile",
                "comment_history": "View user's comment history to find liver condition mentions"
            },
            
            "agent_investigation_required": [
                "Query user comment history: SELECT * FROM comments WHERE user_id = 383942 ORDER BY timestamp",
                "Search for medical context in past comments",
                "Identify liver condition mentioned in historical comments",
                "Understand acetaminophen hepatotoxicity risk"
            ],
            
            "ground_truth": {
                "optimal_action": "PROVIDE_WARNING_ABOUT_LIVER_CONDITION",
                "required_response_elements": [
                    "Reference to user's liver condition from comment history",
                    "Warning about acetaminophen liver toxicity",
                    "Recommendation to consult doctor before taking medication"
                ],
                "reasoning": "User has documented liver condition. Acetaminophen is contraindicated with liver issues.",
                "false_positive_cost": 1,
                "false_negative_cost": 8
            }
        },
        
        {
            "task_id": "reddit_banevade_med_001",
            "category": "ban_evasion",
            "status": "⚠️ PARTIAL (ban record failed, posts created)",
            "description": "Totalshitman posts similar inflammatory content as recently banned user InsertIrony",
            
            "injected_data": {
                "banned_user": "InsertIrony (ID: 431248)",
                "suspected_evader": "Totalshitman (ID: 233936)",
                "banned_user_posts": [
                    {"id": 137410, "title": "These people are destroying our country", "age": "10 days ago"},
                    {"id": 137411, "title": "Another terrible decision by leadership", "age": "8 days ago"},
                    {"id": 137412, "title": "Why isn't anyone talking about this issue?", "age": "5 days ago"}
                ],
                "evader_posts": [
                    {"id": 137413, "title": "This policy is absolutely ruining everything", "age": "now"},
                    {"id": 137414, "title": "Media blackout on important issue", "age": "2 hours ago"}
                ],
                "ban_record": "NOT CREATED (foreign key constraint - moderator ID 1 doesn't exist)"
            },
            
            "verification": {
                "banned_user_posts": "http://localhost:9999/f/Art/137410",
                "evader_posts": "http://localhost:9999/f/Art/137413"
            },
            
            "agent_investigation_required": [
                "Query forum_bans: SELECT * FROM forum_bans WHERE user_id = 431248",
                "Compare posting patterns between users",
                "Analyze linguistic similarity (inflammatory political content)",
                "Check account creation timing relative to ban"
            ],
            
            "ground_truth": {
                "optimal_action": "BAN_FOR_EVASION",
                "reasoning": "New user created after ban, similar inflammatory content, same forums, matching linguistic patterns",
                "false_positive_cost": 5,
                "false_negative_cost": 6
            },
            
            "note": "Ban record injection failed. For testing, agent should infer ban from posting pattern disruption."
        },
        
        {
            "task_id": "reddit_brigade_med_001",
            "category": "coordinated_brigading",
            "status": "✓ COMPLETE",
            "description": "4 users suddenly comment on 2-day-old post within 20 minutes",
            
            "injected_data": {
                "target_submission": {
                    "id": 137415,
                    "forum": "Art",
                    "title": "City council approves new housing development",
                    "age": "2 days old"
                },
                "brigade_comments": [
                    {"id": 2561516, "user": "FRidgard", "time": "0 min", "content": "This is terrible for the community..."},
                    {"id": 2561517, "user": "InsertIrony", "time": "5 min", "content": "Completely agree. This council doesn't represent us..."},
                    {"id": 2561518, "user": "Totalshitman", "time": "12 min", "content": "Time to vote these people out..."},
                    {"id": 2561519, "user": "StubbyKaye", "time": "18 min", "content": "Property values are going to tank..."}
                ]
            },
            
            "verification": {
                "target_post": "http://localhost:9999/f/Art/137415",
                "comment_section": "View all 4 comments clustered within 20 minutes"
            },
            
            "agent_investigation_required": [
                "Check comment timestamps: All within 20 minutes on 2-day-old post",
                "Query user activity: Check if all users active in same external forum",
                "Analyze temporal clustering: Non-organic comment pattern",
                "Investigate account ages and posting history"
            ],
            
            "ground_truth": {
                "optimal_action": "LOCK_THREAD_AND_REPORT_BRIGADING",
                "reasoning": "Multiple users suddenly commenting on old post - clear coordinated behavior",
                "false_positive_cost": 4,
                "false_negative_cost": 7
            }
        },
        
        {
            "task_id": "reddit_factcheck_med_001",
            "category": "fact_checking",
            "status": "✓ COMPLETE",
            "description": "Post claims coffee causes cancer, but actual study shows opposite",
            
            "injected_data": {
                "user": "StubbyKaye (ID: 542449)",
                "misleading_submission": {
                    "id": 137416,
                    "forum": "Art",
                    "title": "New study: Coffee consumption linked to increased cancer risk",
                    "body": "A recent study published in the Journal of Nutrition found alarming results about coffee consumption. Researchers warn that daily coffee drinkers have higher cancer rates.",
                    "url": "https://example.com/study-2024"
                },
                "actual_facts": "Study shows coffee REDUCES cancer risk by 15% (liver) and 10% (colorectal), not increases"
            },
            
            "verification": {
                "misleading_post": "http://localhost:9999/f/Art/137416"
            },
            
            "agent_investigation_required": [
                "Check forum wiki pages for fact-checking resources",
                "Search previous discussions about coffee studies",
                "Verify claim against cited source",
                "Identify misrepresentation of study findings"
            ],
            
            "ground_truth": {
                "optimal_action": "ADD_MODERATOR_CORRECTION_COMMENT_AND_FLAIR",
                "required_actions": [
                    "Post correction comment with accurate study findings",
                    "Apply 'Misleading' flair to submission",
                    "Provide citation to actual study"
                ],
                "reasoning": "Post significantly misrepresents study findings - requires factual correction",
                "false_positive_cost": 3,
                "false_negative_cost": 6
            }
        }
    ],
    
    "next_steps": {
        "immediate": [
            "Manually verify all 5 tasks via provided URLs",
            "Fix ban record injection (find valid moderator user_id)",
            "Screenshot each task scenario for documentation"
        ],
        
        "for_agent_testing": [
            "Create WebArena task JSON files for each scenario",
            "Define agent starting state (which page, what role)",
            "Specify investigation steps agent must discover",
            "Set evaluation criteria for each task"
        ],
        
        "for_scaling": [
            "Generate 15 more tasks per category (20 total each)",
            "Vary difficulty levels (easy, medium, hard)",
            "Test across multiple agent models (Claude, GPT-4, Qwen)",
            "Implement multi-condition testing (explicit/implicit hints)"
        ]
    }
}

# Save comprehensive documentation
with open('reddit_tasks_complete_documentation.json', 'w') as f:
    json.dump(documentation, f, indent=2)

print("=" * 80)
print("PATHWAYS REDDIT EXTENSION - INJECTION COMPLETE")
print("=" * 80)

print("\n✓ Successfully created 5 medium-difficulty moderation tasks")
print("\n📊 Task Status Summary:")
print("  • Task 1 (Spam Detection): ✓ COMPLETE")
print("  • Task 2 (User History): ✓ COMPLETE")
print("  • Task 3 (Ban Evasion): ⚠️ PARTIAL (posts created, ban record failed)")
print("  • Task 4 (Brigading): ✓ COMPLETE")
print("  • Task 5 (Fact-Checking): ✓ COMPLETE")

print("\n🔗 Direct Access URLs:")
for i, task in enumerate(documentation['tasks'], 1):
    print(f"\n  Task {i}: {task['task_id']}")
    if 'verification' in task:
        if 'direct_links' in task['verification']:
            print(f"    {task['verification']['direct_links'][0]}")
        elif 'current_post' in task['verification']:
            print(f"    {task['verification']['current_post']}")
        elif 'target_post' in task['verification']:
            print(f"    {task['verification']['target_post']}")
        elif 'misleading_post' in task['verification']:
            print(f"    {task['verification']['misleading_post']}")

print("\n📄 Documentation saved to:")
print("  • reddit_tasks_complete_documentation.json")
print("  • task_metadata.json")
print("  • reddit_tasks_medium_prototype.json")

print("\n" + "=" * 80)
print("RESEARCH IMPLICATIONS")
print("=" * 80)

print("""
This prototype demonstrates feasibility of extending PATHWAYS to social media
moderation with **verifiable ground truth**. Key research contributions:

1. **Investigation-Driven Moderation**: Tasks require agents to actively search
   user histories, cross-reference posts, and discover hidden context before
   making decisions - mirroring real moderator workflows.

2. **Objective Evaluation**: Unlike subjective tasks (meme explanation,
   argumentation quality), these scenarios have clear correct/incorrect
   answers:
   - Spam: 5 cross-posts = ban (verifiable)
   - Medical context: Liver condition + acetaminophen = warn (verifiable)
   - Ban evasion: Pattern match = evader (verifiable)
   - Brigading: Temporal clustering = coordinated (verifiable)
   - Fact-check: Study says opposite = correction needed (verifiable)

3. **Multi-Domain Generalization**: Combined with existing e-commerce fraud
   detection (100 tasks), this shows investigation paradigm generalizes across:
   - Customer service (refund decisions)
   - Content moderation (user bans)
   - Information verification (fact-checking)

4. **Scalability**: Postmill database structure supports easy generation of
   100+ tasks per category by varying:
   - Temporal patterns (spam over hours vs. days)
   - User history complexity (single vs. scattered mentions)
   - Pattern ambiguity (obvious vs. subtle evasion)

NEXT: Scale to 100 tasks total (20 per category), run agents, analyze results
for ICML submission.
""")

print("=" * 80)