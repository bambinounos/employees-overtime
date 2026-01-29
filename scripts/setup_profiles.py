from employees.models import Employee, JobProfile, KPI

def run():
    print("Initializing Standard Job Profile...")
    
    # 1. Create the Standard Profile
    profile, created = JobProfile.objects.get_or_create(
        name="Standard",
        defaults={
            "description": "Perfil estándar para empleados existentes. Incluye todos los KPIs legados.",
            "earns_commissions": False
        }
    )
    
    if created:
        print(f"Created JobProfile: {profile.name}")
    else:
        print(f"JobProfile {profile.name} already exists.")

    # 2. Assign all existing KPIs to this profile (Legacy Mode)
    all_kpis = KPI.objects.all()
    profile.kpis.set(all_kpis)
    print(f"Assigned {all_kpis.count()} KPIs to 'Standard' profile.")

    # 3. Assign this profile to all employees who don't have one
    employees = Employee.objects.filter(profile__isnull=True)
    count = employees.count()
    for emp in employees:
        emp.profile = profile
        emp.save()
    
    print(f"Assigned 'Standard' profile to {count} employees.")
    print("Done.")

if __name__ == "__main__":
    run()
