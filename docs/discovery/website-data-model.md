# Website data model findings

The website's configured operational store is MySQL. Existing tables remain authoritative; column compatibility must be verified in each environment because several legacy tables are represented by models but not created by migrations in the inspected repository.

| Concept | Verified model/table | Important findings |
|---|---|---|
| Laravel admins | `users` | Standard authenticatable model with Spatie `HasRoles` |
| Legacy identities | `register` | String `user_id`; role/status fields and extensive student/tutor profile fields; no timestamps |
| Tutor offerings | `teacher_course_managment`, `teacher_courses` | Two incompatible representations; one uses category IDs/comma-separated subject IDs, one stores subject/board/class strings |
| Tutor quality | `teacher_review` | Rating plus expertise, patience, reliability, communication; approval semantics require confirmation |
| Student enquiries | `student_enquiry_managment`, `student_enquiry_course` | Legacy user/contact/requirement data with comma-separated subject IDs |
| Demo capture | `demo_leads` | Name/phone/service/subject/class/time/mode/location/message/source only |
| Pricing | `plans`, `subscription_plans` | Two overlapping plan tables; current pricing controller uses `subscription_plans` |
| Legacy commerce | `order_managment`, `order_details` | Misspelled legacy columns and string payment/order state |
| Current subscriptions | `user_subscriptions` | Indexed by user/type but no unique payment activation key or provider order binding |

## Tutor availability gap

No availability/working-hours/exceptions table or model was found. `HomeController` explicitly assigns a placeholder availability score of 70; the value is not included in its weighted score. Marketing/UI references to availability are not an authoritative scheduling source.

## Authentication and authorization

- Super-admin routes use `auth` plus `role:super_admin`.
- `sub_admin` exists with limited permissions but no inspected route group uses it for regional operations.
- No region membership, tenant membership, export scope, or audited region override was found.

## Integration consequence

The website gateway must normalize the two tutor-course shapes, treat review status semantics conservatively, expose authoritative email without leaking it to users, and return `availability_status=unknown` until a reviewed availability source exists.
