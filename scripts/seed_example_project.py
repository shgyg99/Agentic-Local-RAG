from packages.domain.database import get_session_factory
from packages.domain.repositories import ProjectRepository, UserRepository


def seed_example_project() -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        users = UserRepository(session)
        projects = ProjectRepository(session)

        user = users.get_by_email("demo@example.com")
        if user is None:
            user = users.create(email="demo@example.com", display_name="Demo User")

        if not user.projects:
            projects.create(
                owner_id=user.id,
                title="Demo Research Project",
                description="Seed project for local development.",
                research_question="How reliable is the EvidenceFlow retrieval pipeline?",
            )

        session.commit()


if __name__ == "__main__":
    seed_example_project()
    print("Seed data created.")
